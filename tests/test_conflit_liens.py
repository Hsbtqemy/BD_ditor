"""CONC-4 — le locuteur et le personnage montré refusent un enregistrement fait sur une valeur
périmée, comme la note et le texte depuis CONC-3 (Hugo, 2026-10-21 : le patron du temps b).

Mesuré le 2026-10-25 à deux navigateurs, sur le code d'avant : Alice pose Zed sur une bulle,
Bob — dont l'écran montrait « aucun locuteur » — pose Yann ; la base garde Yann, le journal
porte les deux `lien`, et aucun des deux écrans n'en dit rien (Alice montre encore Zed). Pire,
Alice retire alors « son » Zed d'un clic sur ✕ : le retrait emporte Yann, en silence. Le même
pour le personnage montré d'une boîte personnage.

Le remède est celui de CONC-3 : l'écran envoie le personnage qu'il VOYAIT (`personnage_vu`,
un identifiant, ou `null` pour « aucun »), et le serveur refuse par le 409 nommé si la base
porte autre chose. La valeur vue reste FACULTATIVE pour l'API (Q8) : sans elle, le dernier
gagne, comme avant. Ces tests tiennent le serveur ; l'écran a sa garde e2e.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from test_conflit_version import (  # noqa: E402
    A, B, NOMMEE_A, NOMME_B, _derriere_le_proxy, _rendez_vous_apres_lecture, _simultanes)

# (route, clé de la réponse, type de la région, table du journal, champ nommé par le 409)
LOCUTEUR = ("locuteur", "locuteur", "bulle", "bulle_locuteur", "locuteur")
PRESENCE = ("personnage", "personnage", "personnage", "personnage_presence", "presence")


def _region(client, planche_id, type_):
    rep = client.post(f"/api/planches/{planche_id}/regions",
                      json={"type": type_, "x": 0, "y": 0, "w": 10, "h": 10})
    assert rep.status_code in (200, 201), rep.text
    return rep.json()["id"]


def _personnages(client, *noms):
    return [client.post("/api/personnages", json={"nom": n}).json()["id"] for n in noms]


def _actuel(client, route, cle, rid):
    return (client.get(f"/api/regions/{rid}/{route}", headers=A).json()[cle] or {}).get("id")


def _poser(client, route, rid, pid, headers, **vu):
    corps = {"personnage_id": pid}
    if vu:
        corps["personnage_vu"] = vu["vu"]
    return client.put(f"/api/regions/{rid}/{route}", json=corps, headers=headers)


def _retirer(client, route, rid, headers, **vu):
    suffixe = f"?personnage_vu={vu['vu']}" if vu else ""
    return client.delete(f"/api/regions/{rid}/{route}{suffixe}", headers=headers)


def _les_deux(fonction):
    """Joue le même test sur le locuteur d'une bulle et sur le personnage d'une boîte."""
    def locuteur(client, planche, monkeypatch):
        fonction(client, planche, monkeypatch, *LOCUTEUR)

    def presence(client, planche, monkeypatch):
        fonction(client, planche, monkeypatch, *PRESENCE)
    return locuteur, presence


# --------------------------------------------------------------------------- #
# La mesure, rejouée : la seconde attribution est refusée, la première reste
# --------------------------------------------------------------------------- #
def _deux_attributions(client, planche, monkeypatch, route, cle, type_, table, champ):
    rid = _region(client, planche["id"], type_)
    zed, yann = _personnages(client, "Zed", "Yann")
    _derriere_le_proxy(monkeypatch, client)
    assert _poser(client, route, rid, zed, NOMMEE_A, vu=None).status_code == 200

    rep = _poser(client, route, rid, yann, NOMME_B, vu=None)
    assert rep.status_code == 409, rep.text
    d = rep.json()["detail"]
    c = d["conflit"]
    assert (c["cible"], c["id"], c["champ"]) == (table, rid, champ)
    assert c["valeur_actuelle"] == zed
    # De quoi montrer la version de l'autre sans relire : le personnage, nommé.
    assert c["personnage"]["id"] == zed and c["personnage"]["nom"] == "Zed"
    assert (c["auteur"]["nom"], c["auteur"]["login"], c["auteur"]["meme_compte"]) == (
        "Alice Dupont", "personne-a", False)
    assert "Alice Dupont" in d["message"]
    assert _actuel(client, route, cle, rid) == zed, "le choix d'Alice a été écrasé"


(test_deux_locuteurs_le_second_est_refuse_et_nomme_le_premier,
 test_deux_personnages_montres_le_second_est_refuse_et_nomme_le_premier) = \
    _les_deux(_deux_attributions)


def _retrait_perime(client, planche, monkeypatch, route, cle, type_, table, champ):
    """La seconde moitié de la mesure : Alice voit encore Zed, Bob l'a remplacé par Yann ;
    le ✕ d'Alice ne retire plus Yann."""
    rid = _region(client, planche["id"], type_)
    zed, yann = _personnages(client, "Zed", "Yann")
    _derriere_le_proxy(monkeypatch, client)
    assert _poser(client, route, rid, zed, NOMMEE_A, vu=None).status_code == 200
    assert _poser(client, route, rid, yann, NOMME_B, vu=zed).status_code == 200

    rep = _retirer(client, route, rid, NOMMEE_A, vu=zed)
    assert rep.status_code == 409, rep.text
    c = rep.json()["detail"]["conflit"]
    assert (c["champ"], c["valeur_actuelle"], c["auteur"]["login"]) == (champ, yann, "personne-b")
    assert c["personnage"]["nom"] == "Yann"
    assert _actuel(client, route, cle, rid) == yann, "le retrait d'Alice a emporté Yann"


(test_retirer_un_locuteur_change_depuis_est_refuse,
 test_retirer_un_personnage_montre_change_depuis_est_refuse) = _les_deux(_retrait_perime)


def _une_attribution_apres_un_retrait(client, planche, monkeypatch, route, cle, type_, table,
                                      champ):
    """Bob a retiré le personnage qu'Alice voyait : l'attribution d'Alice est refusée aussi —
    son écran ne savait pas que la place était libre. Le 409 dit « aucun »."""
    rid = _region(client, planche["id"], type_)
    zed, yann = _personnages(client, "Zed", "Yann")
    _derriere_le_proxy(monkeypatch, client)
    assert _poser(client, route, rid, zed, NOMMEE_A, vu=None).status_code == 200
    assert _retirer(client, route, rid, NOMME_B, vu=zed).status_code == 204
    rep = _poser(client, route, rid, yann, NOMMEE_A, vu=zed)
    assert rep.status_code == 409, rep.text
    c = rep.json()["detail"]["conflit"]
    assert (c["valeur_actuelle"], c["personnage"], c["auteur"]["login"]) == (
        None, None, "personne-b")
    assert _actuel(client, route, cle, rid) is None


(test_un_locuteur_retire_ailleurs_refuse_l_attribution_qui_le_croyait_la,
 test_un_personnage_retire_ailleurs_refuse_l_attribution_qui_le_croyait_la) = \
    _les_deux(_une_attribution_apres_un_retrait)


# --------------------------------------------------------------------------- #
# Ce qui passe : rien ne se perd, ou l'appelant n'a rien déclaré (Q8)
# --------------------------------------------------------------------------- #
def _sans_valeur_vue(client, planche, monkeypatch, route, cle, type_, table, champ):
    """Q8 — la valeur vue est FACULTATIVE : outils et appelants existants gardent « le dernier
    gagne », pour l'attribution comme pour le retrait."""
    rid = _region(client, planche["id"], type_)
    zed, yann = _personnages(client, "Zed", "Yann")
    _derriere_le_proxy(monkeypatch, client)
    assert _poser(client, route, rid, zed, A).status_code == 200
    assert _poser(client, route, rid, yann, B).status_code == 200
    assert _actuel(client, route, cle, rid) == yann
    assert _retirer(client, route, rid, A).status_code == 204
    assert _actuel(client, route, cle, rid) is None


(test_sans_valeur_vue_le_dernier_locuteur_gagne_comme_avant,
 test_sans_valeur_vue_le_dernier_personnage_gagne_comme_avant) = _les_deux(_sans_valeur_vue)


def _rien_ne_se_perd(client, planche, monkeypatch, route, cle, type_, table, champ):
    """Poser ce que la base porte déjà, ou retirer ce qui est déjà retiré : l'écran était en
    retard, mais le conflit n'aurait rien à montrer (la règle de `conflit.verifier`)."""
    rid = _region(client, planche["id"], type_)
    (zed,) = _personnages(client, "Zed")
    _derriere_le_proxy(monkeypatch, client)
    assert _poser(client, route, rid, zed, A, vu=None).status_code == 200
    assert _poser(client, route, rid, zed, B, vu=None).status_code == 200
    assert _retirer(client, route, rid, A, vu=zed).status_code == 204
    assert _retirer(client, route, rid, B, vu=zed).status_code == 204
    assert _actuel(client, route, cle, rid) is None


(test_poser_le_meme_locuteur_ou_retirer_un_retire_n_est_pas_un_conflit,
 test_poser_le_meme_personnage_ou_retirer_un_retire_n_est_pas_un_conflit) = \
    _les_deux(_rien_ne_se_perd)


def test_la_valeur_vue_d_un_retrait_doit_etre_un_identifiant(client, planche):
    rid = _region(client, planche["id"], "bulle")
    assert client.delete(f"/api/regions/{rid}/locuteur?personnage_vu=zed").status_code == 422


# --------------------------------------------------------------------------- #
# Qui nommer : le journal du lien, et le changement de type qui l'a retiré
# --------------------------------------------------------------------------- #
def test_un_locuteur_ote_par_un_changement_de_type_nomme_qui_a_change_le_type(
        client, planche, monkeypatch):
    """ANN-8 — passer une bulle en case lui retire son locuteur, dans un acte sur `regions`.
    Repassée en bulle, la place est libre ; l'écran d'Alice voyait encore Zed. Le 409 nomme
    Bob, qui a changé le type — `auteur_des_champs` lit les deux sortes d'actes."""
    rid = _region(client, planche["id"], "bulle")
    zed, yann = _personnages(client, "Zed", "Yann")
    _derriere_le_proxy(monkeypatch, client)
    assert _poser(client, "locuteur", rid, zed, NOMMEE_A, vu=None).status_code == 200
    assert client.put(f"/api/regions/{rid}", json={"type": "case"},
                      headers=NOMME_B).status_code == 200
    assert client.put(f"/api/regions/{rid}", json={"type": "bulle"},
                      headers=NOMME_B).status_code == 200
    rep = _poser(client, "locuteur", rid, yann, NOMMEE_A, vu=zed)
    assert rep.status_code == 409, rep.text
    assert rep.json()["detail"]["conflit"]["auteur"]["login"] == "personne-b"


def test_le_meme_compte_ne_se_nomme_pas_lui_meme(client, planche, monkeypatch):
    """Deux onglets d'une même personne, ou un compte partagé (Q7 de CONC-3)."""
    rid = _region(client, planche["id"], "bulle")
    zed, yann = _personnages(client, "Zed", "Yann")
    _derriere_le_proxy(monkeypatch, client)
    assert _poser(client, "locuteur", rid, zed, NOMMEE_A, vu=None).status_code == 200
    rep = _poser(client, "locuteur", rid, yann, NOMMEE_A, vu=None)
    assert rep.status_code == 409, rep.text
    assert rep.json()["detail"]["conflit"]["auteur"]["meme_compte"] is True
    assert "même compte" in rep.json()["detail"]["message"]


def test_un_conflit_n_ecrit_rien_au_journal(client, planche, monkeypatch, db_path):
    from conftest import direct_query
    rid = _region(client, planche["id"], "bulle")
    zed, yann = _personnages(client, "Zed", "Yann")
    _derriere_le_proxy(monkeypatch, client)
    assert _poser(client, "locuteur", rid, zed, A, vu=None).status_code == 200
    n = direct_query(db_path, "SELECT COUNT(*) n FROM evenement")[0]["n"]
    assert _poser(client, "locuteur", rid, yann, B, vu=None).status_code == 409
    assert _retirer(client, "locuteur", rid, B, vu=yann).status_code == 409
    assert direct_query(db_path, "SELECT COUNT(*) n FROM evenement")[0]["n"] == n


# --------------------------------------------------------------------------- #
# La course : la garde lit sous le verrou d'écriture
# --------------------------------------------------------------------------- #
def _course(client, planche, monkeypatch, route, cle, type_, table, champ):
    """Deux attributions simultanées, toutes deux sur « aucun » : sans le verrou pris AVANT de
    lire le lien actuel, les deux lisaient « aucun », passaient, et la seconde écrasait la
    première sans 409 (le défaut que CONC-3 a trouvé sur la note, `ab1a7e3`)."""
    rid = _region(client, planche["id"], type_)
    zed, yann = _personnages(client, "Zed", "Yann")
    _rendez_vous_apres_lecture(monkeypatch)
    issues = _simultanes([
        lambda: _poser(client, route, rid, zed, A, vu=None),
        lambda: _poser(client, route, rid, yann, B, vu=None)])
    assert sorted(issues) == ["conflit", "ok"], issues
    assert _actuel(client, route, cle, rid) == (zed if issues[0] == "ok" else yann)


(test_deux_locuteurs_simultanes_ne_passent_pas_tous_deux_la_garde,
 test_deux_personnages_simultanes_ne_passent_pas_tous_deux_la_garde) = _les_deux(_course)


def test_un_retrait_et_une_attribution_simultanes_ne_passent_pas_tous_deux(
        client, planche, monkeypatch):
    rid = _region(client, planche["id"], "bulle")
    zed, yann = _personnages(client, "Zed", "Yann")
    assert _poser(client, "locuteur", rid, zed, A).status_code == 200
    _rendez_vous_apres_lecture(monkeypatch)
    issues = _simultanes([
        lambda: _retirer(client, "locuteur", rid, A, vu=zed),
        lambda: _poser(client, "locuteur", rid, yann, B, vu=zed)])
    assert all(i in ("ok", "conflit") or i.startswith("204") for i in issues), issues
    # Le retrait rend 204, compté hors de « ok » par `_simultanes` : l'un des deux, et un seul,
    # est un conflit.
    assert issues.count("conflit") == 1, issues
    gagnant = None if issues[1] == "conflit" else yann
    assert _actuel(client, "locuteur", "locuteur", rid) == gagnant
