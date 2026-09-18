"""AUTH-12 étape 4 — le référent de l'INSTANCE, constaté par qui peut le régler.

`BD_REFERENT_NOM` / `BD_REFERENT_CONTACT` (AUTH-4) existent depuis le 2026-09-06 et ne se
voyaient QUE dans le bandeau de portée vide, c'est-à-dire par qui n'a accès à rien. Celui
qui pourrait les corriger ne les voyait jamais : personne ne remarquait qu'ils manquent ou
qu'ils ont vieilli, et un `.env` recréé repartait sans eux sans qu'aucun signal ne le dise.
C'est l'oubli constaté sur la production le 2026-09-09 — fonctionnalité livrée, jamais
configurée.

`GET /api/referent` est l'endroit où ça se constate. Décision 6 (b) de Hugo, 2026-09-17 :
l'Administration AFFICHE, elle ne règle pas — le réglage reste dans l'environnement du
serveur, et l'option de le stocker en base a été écartée parce qu'il change rarement.

**CE QUE CE FICHIER GARDE AVANT TOUT, c'est le TROISIÈME état.** `_referent_instance()`
rend un dict dès qu'UN des deux est posé, si bien qu'un référent nommé SANS contact est
atteignable. C'est le pire des trois : le bandeau nomme alors quelqu'un sans dire comment
l'atteindre, à une personne qui ne peut rien faire d'autre que le contacter. Ce n'est pas
un demi-référent, c'est un cul-de-sac qui a l'air d'une réponse — et il est le seul des
trois à TROMPER celui qui le lit.
"""
import pytest

import main
from conftest import ADMIN


# --------------------------------------------------------------------------- #
# La garde
# --------------------------------------------------------------------------- #
def test_le_referent_est_reserve_aux_administrateurs(client, derriere_proxy):
    """Réservé, alors que le référent n'est PAS un secret — et la nuance est le sujet.

    Ce 403 dit « cette VUE n'est pas pour vous », jamais « cette donnée est secrète » :
    constater un réglage de serveur n'intéresse que qui exploite l'instance. La donnée,
    elle, reste ouverte à tous par `/api/moi` — c'est le test du bas, et il existe pour
    qu'on ne « répare » pas l'incohérence apparente dans le mauvais sens.
    """
    r = client.get("/api/referent", headers={"Remote-User": "simple"})
    assert r.status_code == 403
    assert "administrateurs" in r.json()["detail"]


def test_en_mono_poste_le_referent_se_lit_sans_en_tete(client):
    """Sans `BD_AUTH_PROXY`, la portée est TOTALE : il n'y a personne à qui le cacher.

    Même raison que `/api/version`, et que `acces.groupes_admin` vide en mono-poste."""
    assert client.get("/api/referent").status_code == 200


# --------------------------------------------------------------------------- #
# Les trois états, tranchés par le SERVEUR
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("nom, contact, etat", [
    ("Ana Ruiz", "ana@labo.fr", "joignable"),
    ("",         "ana@labo.fr", "joignable"),   # une adresse sans nom REste une adresse
    ("Ana Ruiz", "",            "injoignable"),  # le cul-de-sac
    ("",         "",            "absent"),
])
def test_les_trois_etats_sont_tranches_par_le_serveur(client, derriere_proxy, monkeypatch,
                                                      nom, contact, etat):
    """L'état est une RÈGLE, et elle a une seule source.

    L'écran saurait la déduire — `referent` nul, puis `contact` nul — mais elle serait
    alors écrite à deux endroits, et c'est celle de l'écran qui dériverait sans que rien
    ne tombe. Le remplacement porte sur `main.*` parce que `main.py` importe les constantes
    de `config` PAR VALEUR : second critère d'ARCH-1, et cette route reste donc dans
    `main.py`, à côté de `/api/version` épinglée pour la même raison.
    """
    monkeypatch.setattr(main, "REFERENT_NOM", nom)
    monkeypatch.setattr(main, "REFERENT_CONTACT", contact)
    assert client.get("/api/referent", headers=ADMIN).json()["etat"] == etat


def test_un_referent_nomme_sans_contact_est_signale_comme_un_cul_de_sac(
        client, derriere_proxy, monkeypatch):
    """LE test du chantier : l'état qui trompe, et qu'aucun `null` ne signale.

    Un `.env` à moitié rempli ne casse rien et ne rend rien vide — il produit un bandeau
    qui NOMME quelqu'un. La personne bloquée croit tenir une réponse et n'a aucune adresse ;
    l'administrateur, lui, voit un référent déclaré et passe son chemin. La note doit donc
    nommer la variable qui manque, et elle seule : envoyer reposer les deux ferait douter
    de celle qui est juste.
    """
    monkeypatch.setattr(main, "REFERENT_NOM", "Ana Ruiz")
    monkeypatch.setattr(main, "REFERENT_CONTACT", "")
    d = client.get("/api/referent", headers=ADMIN).json()
    assert d["etat"] == "injoignable"
    assert d["referent"] == {"nom": "Ana Ruiz", "contact": None}
    assert d["note"] and "BD_REFERENT_CONTACT" in d["note"]
    assert "BD_REFERENT_NOM" not in d["note"]


def test_sans_referent_la_route_DIT_ce_que_ca_coute_et_ou_le_poser(
        client, derriere_proxy, monkeypatch):
    """Un `null` seul ne dit ni le coût ni le remède — même raison que `/api/version`.

    C'est l'état par DÉFAUT en local et sur un `.env` recréé, donc celui qu'on verra le
    plus souvent : il doit être le plus clair des trois.
    """
    monkeypatch.setattr(main, "REFERENT_NOM", "")
    monkeypatch.setattr(main, "REFERENT_CONTACT", "")
    d = client.get("/api/referent", headers=ADMIN).json()
    assert d["etat"] == "absent"
    assert d["referent"] is None
    assert d["note"]
    assert "BD_REFERENT_NOM" in d["note"] and "BD_REFERENT_CONTACT" in d["note"]


def test_quand_tout_va_bien_la_route_n_explique_rien(client, derriere_proxy, monkeypatch):
    """`note` porte ce qu'un `null` ne dit pas ; sans `null`, elle n'a rien à dire."""
    monkeypatch.setattr(main, "REFERENT_NOM", "Ana Ruiz")
    monkeypatch.setattr(main, "REFERENT_CONTACT", "ana@labo.fr")
    d = client.get("/api/referent", headers=ADMIN).json()
    assert d["etat"] == "joignable"
    assert d["referent"] == {"nom": "Ana Ruiz", "contact": "ana@labo.fr"}
    assert d["note"] is None


# --------------------------------------------------------------------------- #
# L'invariant qu'il ne faut PAS « réparer »
# --------------------------------------------------------------------------- #
def test_api_moi_sert_le_referent_a_TOUT_LE_MONDE(client, derriere_proxy, monkeypatch):
    """Le 403 d'à côté ne doit JAMAIS se propager ici, et ce test est là pour le dire.

    Un lecteur qui verrait `/api/referent` réservée et `/api/moi` ouverte conclurait à une
    fuite et fermerait la seconde. Ce serait casser le seul usage qui compte : le bandeau
    de portée vide est l'endroit où le référent doit atteindre quelqu'un qui ne voit RIEN,
    et cette personne n'est administratrice de rien. Les deux routes servent la même
    donnée à deux publics, et c'est voulu.
    """
    monkeypatch.setattr(main, "REFERENT_NOM", "Ana Ruiz")
    monkeypatch.setattr(main, "REFERENT_CONTACT", "ana@labo.fr")
    d = client.get("/api/moi", headers={"Remote-User": "sans-acces"}).json()
    assert d["acces"]["referent"] == {"nom": "Ana Ruiz", "contact": "ana@labo.fr"}
    assert d["acces"]["total"] is False, "le décor doit bien être une portée non totale"
