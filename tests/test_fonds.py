"""COL-3, tranche 2 — « supprimer » a deux réponses, la demande, et le fonds côté serveur.

Les décisions de Hugo (2026-10-11) que ces tests tiennent :

- B2 : « Supprimer définitivement » efface sans rien demander quand l'appelant a importé le
  document et que personne d'autre n'y a travaillé ; la règle d'AUTH-10 (écrire dans toutes
  ses collections) est gardée en plus. Un travail supprimé depuis ne compte plus ; une
  reconnaissance automatique lancée par un collègue ne compte pas.
- B3 : un album d'avant le fonds, d'importateur inconnu, se demande — seul un
  administrateur le détruit.
- B4 : une planche se supprime là où l'on pourrait supprimer le document, sans demande.
- B5 : le responsable d'un projet DEMANDE sa suppression ; un projet n'est supprimé que vide.
- « Importer au fonds », réservé aux administrateurs, puis « Rendre à… ».

Et les propositions du cadrage suivies en route : R2 (le nom du demandeur se lit sur
l'album), R3 (le motif est obligatoire), R4 (« garder » clôt la demande, qu'on peut
redéposer, et l'administrateur voit le refus antérieur), R6 (le refus de supprimer une
collection reste), R7 (un compte partagé ne supprime jamais définitivement seul).

Chaque geste est joué sous l'identité qui compte, et l'on regarde ensuite ce que voient les
AUTRES, et la base : un code de retour seul ne dit pas si l'album a survécu.
"""
import json
import sqlite3

import pytest

import autorisation
import comptes
import database
import main
import socle
from conftest import ADMIN, make_png
from test_projets import _fouillable, _outil, _repli, _sql

IMPORTEUSE = {"Remote-User": "importeuse"}      # écrit dans Principale et Incubateur
COLLEGUE = {"Remote-User": "collegue"}          # écrit dans Principale
LECTRICE = {"Remote-User": "lectrice"}          # lit Principale
ATELIER = {"Remote-User": "atelier"}            # écrit dans Principale ; compte partagé


# --------------------------------------------------------------------------- #
# Outils de décor
# --------------------------------------------------------------------------- #
def _collection(client, nom, projet_id=None):
    charge = {"nom": nom} if projet_id is None else {"nom": nom, "projet_id": projet_id}
    r = client.post("/api/collections", json=charge, headers=ADMIN)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _accorder(client, cid, principal, niveau):
    r = client.put(f"/api/collections/{cid}/acces", headers=ADMIN,
                   json={"genre": "utilisateur", "principal": principal, "niveau": niveau})
    assert r.status_code == 200, r.text


def _album(client, titre, cid, qui):
    r = client.post("/api/albums", json={"titre": titre, "collection_id": cid}, headers=qui)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _planche(client, album_id, qui):
    r = client.post(f"/api/albums/{album_id}/import", headers=qui,
                    files={"file": ("p.png", make_png(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _region(client, planche_id, qui):
    r = client.post(f"/api/planches/{planche_id}/regions", headers=qui,
                    json={"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _albums(client, qui):
    return {a["id"]: a for a in client.get("/api/albums", headers=qui).json()}


def _demander(client, album_id, qui, motif="Importé par erreur", certifie=True):
    """Déposer une demande de suppression, CERTIFIÉE par défaut (Hugo, 2026-10-15) : la
    case est exigée, et les tests qui ne la mesurent pas la cochent comme l'écran."""
    return client.post("/api/demandes", headers=qui,
                       json={"genre": "suppression_document", "album_id": album_id,
                             "motif": motif, "certifie": certifie})


def _repondre(client, demande_id, reponse, qui=ADMIN):
    return client.post(f"/api/demandes/{demande_id}/reponse", headers=qui,
                       json={"reponse": reponse})


def _fichiers(data_dir, album_id):
    return [d for d in (data_dir / "corpus" / f"album_{album_id}",
                        data_dir / "derivatives" / f"album_{album_id}") if d.exists()]


@pytest.fixture
def decor(client, derriere_proxy, data_dir):
    """Deux collections du projet de repli, quatre comptes, et « Erreur » : un album importé
    par `importeuse` dans Principale, une planche (importée par elle), une région (posée
    par elle). Personne d'autre n'y a touché : c'est l'import par erreur."""
    principale, incubateur = _collection(client, "Principale"), _collection(client, "Incubateur")
    for cid, qui, niveau in ((principale, "importeuse", "ecriture"),
                             (incubateur, "importeuse", "ecriture"),
                             (principale, "collegue", "ecriture"),
                             (principale, "lectrice", "lecture"),
                             (principale, "atelier", "ecriture")):
        _accorder(client, cid, qui, niveau)
    erreur = _album(client, "Erreur", principale, IMPORTEUSE)
    planche = _planche(client, erreur, IMPORTEUSE)
    region = _region(client, planche, IMPORTEUSE)
    return {"principale": principale, "incubateur": incubateur, "erreur": erreur,
            "planche": planche, "region": region, "data": data_dir}


# =========================================================================== #
# B2 — qui supprime définitivement, sans rien demander
# =========================================================================== #
def test_qui_a_importe_seul_supprime_tout_de_suite(client, db_path, decor):
    """L'import par erreur ne doit attendre personne. Et « tout de suite » veut dire tout :
    la ligne, le document, les images sur le disque, et un acte au journal."""
    aid = decor["erreur"]
    doc = _sql(db_path, "SELECT document_id FROM albums WHERE id = ?", (aid,))[0]["document_id"]
    assert _albums(client, IMPORTEUSE)[aid]["destructible"] is True
    assert _fichiers(decor["data"], aid), "le décor n'a pas posé d'images"

    assert client.delete(f"/api/albums/{aid}", headers=IMPORTEUSE).status_code == 204
    assert aid not in _albums(client, ADMIN)
    assert _sql(db_path, "SELECT 1 FROM document WHERE id = ?", (doc,)) == []
    assert _fichiers(decor["data"], aid) == []
    assert _sql(db_path, "SELECT agent FROM evenement WHERE cible_table = 'document' "
                         "AND type = 'suppression' AND cible_id = ?", (doc,)) \
        == [{"agent": "importeuse"}]


def _personnage(client, qui):
    r = client.post("/api/personnages", json={"nom": "Haddock"}, headers=qui)
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _locuteur(client, decor):
    r = client.put(f"/api/regions/{decor['region']}/locuteur", headers=COLLEGUE,
                   json={"personnage_id": _personnage(client, COLLEGUE)})
    assert r.status_code == 200, r.text


def _presence(client, decor):
    # La boîte personnage est posée par l'importatrice : seule la PRÉSENCE est d'un autre.
    r = client.post(f"/api/planches/{decor['planche']}/regions", headers=IMPORTEUSE,
                    json={"type": "personnage", "x": 0, "y": 0, "w": 9, "h": 9})
    assert r.status_code == 201, r.text
    r = client.put(f"/api/regions/{r.json()['id']}/personnage", headers=COLLEGUE,
                   json={"personnage_id": _personnage(client, COLLEGUE)})
    assert r.status_code == 200, r.text


def _valeur_de_case(client):
    r = client.post("/api/attributs/dimensions", headers=ADMIN,
                    json={"cible": "case", "nom": "émotion"})
    assert r.status_code == 201, r.text
    v = client.post(f"/api/attributs/dimensions/{r.json()['id']}/valeurs", headers=ADMIN,
                    json={"valeur": "colère"})
    assert v.status_code == 201, v.text
    return v.json()["id"]


def _case(client, decor):
    """La case de l'album, posée par l'importatrice à la première demande : depuis ANN-8,
    seule une case reçoit une situation (422 ailleurs), et la région du décor est une bulle."""
    if "case" not in decor:
        r = client.post(f"/api/planches/{decor['planche']}/regions", headers=IMPORTEUSE,
                        json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9})
        assert r.status_code == 201, r.text
        decor["case"] = r.json()["id"]
    return decor["case"]


def _attribut(client, decor, qui=COLLEGUE):
    r = client.put(f"/api/regions/{_case(client, decor)}/attributs", headers=qui,
                   json={"valeur_id": _valeur_de_case(client)})
    assert r.status_code == 200, r.text


def _notice(client, decor):
    r = client.put(f"/api/albums/{decor['erreur']}", headers=COLLEGUE,
                   json={"isbn": "978-2-203-00101-0"})
    assert r.status_code == 200, r.text


def _contribution(client, decor):
    r = client.post(f"/api/albums/{decor['erreur']}/contributions", headers=COLLEGUE,
                    json={"nom": "Hergé", "role": "scénariste"})
    assert r.status_code == 201, r.text


def _relecture(client, decor):
    r = client.patch(f"/api/planches/{decor['planche']}/relecture", headers=COLLEGUE,
                     json={"relecture": "faite"})
    assert r.status_code == 200, r.text


TRAVAUX = {
    "une région posée": lambda c, d: _region(c, d["planche"], COLLEGUE),
    # Relecture croisée de la tranche 2 (sondes S1 à S3) : ces quatre gestes n'étaient
    # écrits nulle part, et l'importatrice détruisait sans demander.
    "un attribut de case": _attribut,
    "la notice": _notice,
    "une contribution": _contribution,
    "une relecture forcée": _relecture,
    "un locuteur": _locuteur,
    "une présence": _presence,
    "une annotation": lambda c, d: c.put(
        f"/api/regions/{d['region']}/annotation", headers=COLLEGUE,
        json={"note": "vu", "tags": []}).raise_for_status(),
    "un scan ajouté": lambda c, d: _planche(c, d["erreur"], COLLEGUE),
    "une planche validée": lambda c, d: c.patch(
        f"/api/planches/{d['planche']}/validation", headers=COLLEGUE,
        json={"validee": True}).raise_for_status(),
}


@pytest.mark.parametrize("travail", sorted(TRAVAUX))
def test_le_travail_d_un_autre_fait_demander(client, decor, travail):
    """Personne d'autre que l'importatrice ne doit y avoir travaillé. Chaque source du
    journal que la règle lit est jouée PAR UN AUTRE, par la route : une moitié qu'on
    oublierait laisserait détruire le travail d'un collègue sans rien lui demander."""
    TRAVAUX[travail](client, decor)
    aid = decor["erreur"]
    assert _albums(client, IMPORTEUSE)[aid]["destructible"] is False
    r = client.delete(f"/api/albums/{aid}", headers=IMPORTEUSE)
    assert r.status_code == 403, r.text
    r = client.delete(f"/api/planches/{decor['planche']}", headers=IMPORTEUSE)
    assert r.status_code == 403 and "planches" in r.json()["detail"], r.text
    assert aid in _albums(client, LECTRICE)
    assert decor["planche"] in [p["id"] for p in client.get(
        f"/api/albums/{aid}/planches", headers=ADMIN).json()]


def test_ses_propres_gestes_ne_font_pas_demander(client, decor):
    """L'envers des travaux d'autrui : les mêmes gestes, faits par l'importatrice, ne lui
    retirent rien — sans quoi « personne d'autre » se réduirait à « personne »."""
    _attribut(client, decor, IMPORTEUSE)
    for chemin, charge in ((f"/api/albums/{decor['erreur']}", {"isbn": "978-2"}),):
        assert client.put(chemin, headers=IMPORTEUSE, json=charge).status_code == 200
    assert client.post(f"/api/albums/{decor['erreur']}/contributions", headers=IMPORTEUSE,
                       json={"nom": "Hergé"}).status_code == 201
    assert client.patch(f"/api/planches/{decor['planche']}/relecture", headers=IMPORTEUSE,
                        json={"relecture": "faite"}).status_code == 200
    assert _albums(client, IMPORTEUSE)[decor["erreur"]]["destructible"] is True


def test_un_attribut_dont_on_ne_sait_pas_qui_l_a_pose_fait_demander(client, db_path, decor):
    """La prudence de B3, appliquée à l'auteur : un attribut de case que rien n'attribue à
    l'importatrice — posé avant que le geste s'écrive, recopié par une fusion de valeurs —
    compte comme le travail d'un autre."""
    vid = _valeur_de_case(client)
    _sql(db_path, "INSERT INTO region_attribut (region_id, valeur_id) VALUES (?, ?)",
         (decor["region"], vid))
    assert _albums(client, IMPORTEUSE)[decor["erreur"]]["destructible"] is False


def test_un_attribut_sans_auteur_le_reste_si_l_importatrice_en_a_retire_un_pareil(
        client, db_path, decor):
    """Un attribut que rien n'attribue — posé avant que le geste s'écrive, puis retiré par
    l'importatrice, puis recopié par la fusion de deux valeurs — reste d'un auteur inconnu :
    seul un `lien` écrit l'attribue, un `delien` ne dit pas qui l'avait posé."""
    vid = _valeur_de_case(client)
    _sql(db_path, "INSERT INTO region_attribut (region_id, valeur_id) VALUES (?, ?)",
         (decor["region"], vid))
    assert client.delete(f"/api/regions/{decor['region']}/attributs/{vid}",
                         headers=IMPORTEUSE).status_code == 204
    _sql(db_path, "INSERT INTO region_attribut (region_id, valeur_id) VALUES (?, ?)",
         (decor["region"], vid))
    assert _albums(client, IMPORTEUSE)[decor["erreur"]]["destructible"] is False


def test_un_attribut_pose_puis_retire_par_un_autre_compte_encore(client, db_path, decor):
    """Comme une annotation posée puis retirée : le journal garde l'acte d'un autre sur une
    région qui vit encore, et c'est lui qui compte — il ne reste plus d'attribut à lire."""
    _attribut(client, decor)
    vid = _sql(db_path, "SELECT valeur_id FROM region_attribut")[0]["valeur_id"]
    assert client.delete(f"/api/regions/{decor['case']}/attributs/{vid}",
                         headers=COLLEGUE).status_code == 204
    assert _sql(db_path, "SELECT 1 FROM region_attribut") == []
    assert _albums(client, IMPORTEUSE)[decor["erreur"]]["destructible"] is False


def test_un_attribut_de_case_s_ecrit_sans_rang_ni_annulation(client, db_path, decor):
    """Écrire un geste neuf au journal change ce qu'on compte. Ce qui change est voulu : le
    collègue qui n'a fait que qualifier une case « laisse des actes » en partant — c'est du
    travail. Ce qui ne change pas est tenu ici : aucun pseudonyme de sortie ne bouge (la
    cible est sans rang), et Ctrl+Z ne défait pas l'attribut — il ne le défaisait pas la
    veille."""
    import _commun

    def conn():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        return c

    _case(client, decor)                 # posée d'abord : elle compte pour l'importatrice
    rangs = _commun.pseudonymes(conn())
    actes = comptes.traces(conn())[0]
    _attribut(client, decor)
    assert _sql(db_path, "SELECT type, agent, cible_id FROM evenement "
                         "WHERE cible_table = 'region_attribut'") == [
        {"type": "lien", "agent": "collegue", "cible_id": decor["case"]}]
    assert _commun.pseudonymes(conn()) == rangs and "collegue" not in rangs
    assert comptes.traces(conn())[0] == {**actes, "collegue": actes.get("collegue", 0) + 1}
    assert client.get("/api/undo/prochain", headers=COLLEGUE).json() is None
    # Retirer s'écrit aussi ; re-retirer ce qui n'est plus là, non.
    vid = _sql(db_path, "SELECT valeur_id FROM region_attribut")[0]["valeur_id"]
    for _ in range(2):
        client.delete(f"/api/regions/{decor['case']}/attributs/{vid}", headers=COLLEGUE)
    assert [e["type"] for e in _sql(db_path, "SELECT type FROM evenement "
                                              "WHERE cible_table = 'region_attribut'")]         == ["lien", "delien"]


def test_la_notice_la_paternite_et_la_relecture_s_ecrivent_sous_le_document(
        client, db_path, decor):
    """Sous le DOCUMENT, cible retenue, sans rang, hors du travail laissé et hors de
    l'annulation : ces gestes s'écrivent sans rien changer à ce qui sort, ni aux comptes.
    Une notice renvoyée telle quelle n'écrit rien."""
    import _commun

    def conn():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        return c

    rangs, actes = _commun.pseudonymes(conn()), comptes.traces(conn())[0]
    avant = len(_sql(db_path, "SELECT 1 FROM evenement WHERE cible_table = 'document'"))
    assert client.put(f"/api/albums/{decor['erreur']}", headers=COLLEGUE,
                      json={"titre": "Erreur"}).status_code == 200      # inchangé
    _notice(client, decor)
    _contribution(client, decor)
    _relecture(client, decor)
    lignes = _sql(db_path, "SELECT agent, apres FROM evenement WHERE cible_table = 'document' "
                           "ORDER BY id")[avant:]
    assert [(l["agent"], sorted(json.loads(l["apres"]))) for l in lignes] == [
        ("collegue", ["album_id", "notice"]), ("collegue", ["album_id", "contribution"]),
        ("collegue", ["album_id", "planche", "relecture"])]
    assert _commun.pseudonymes(conn()) == rangs
    assert comptes.traces(conn())[0] == actes
    assert client.get("/api/undo/prochain", headers=COLLEGUE).json() is None


def test_une_correction_grammaticale_d_un_autre_compte(client, db_path, decor):
    """La correction d'un mot est une couche à part : le journal ne la relie à sa région que
    par l'id de la correction. La règle lit donc son `auteur`."""
    _sql(db_path, "INSERT INTO token_correction (region_id, ordre, forme, auteur) "
                  "VALUES (?, 0, 'OTAGE', 'collegue')", (decor["region"],))
    assert _albums(client, IMPORTEUSE)[decor["erreur"]]["destructible"] is False
    _sql(db_path, "UPDATE token_correction SET auteur = 'importeuse'")
    assert _albums(client, IMPORTEUSE)[decor["erreur"]]["destructible"] is True


def test_une_passe_automatique_ne_compte_pas_un_acte_sans_agent_si(client, db_path, decor):
    """« Une reconnaissance automatique lancée par un collègue ne compte pas » : elle n'est
    attribuée qu'à son moteur. Un acte HUMAIN sans agent, lui, compte — on ne sait pas que
    c'est l'importatrice qui l'a posé."""
    _sql(db_path, "INSERT INTO evenement (type, agent, agent_type, cible_table, cible_id) "
                  "VALUES ('creation', 'kumiko', 'moteur', 'regions', ?)", (decor["region"],))
    assert _albums(client, IMPORTEUSE)[decor["erreur"]]["destructible"] is True
    _sql(db_path, "INSERT INTO evenement (type, agent, agent_type, cible_table, cible_id) "
                  "VALUES ('modification', NULL, 'humain', 'regions', ?)", (decor["region"],))
    assert _albums(client, IMPORTEUSE)[decor["erreur"]]["destructible"] is False


def test_un_travail_supprime_depuis_ne_compte_plus(client, decor):
    """La limite écrite dans la règle, et acceptée par Hugo : on lit ce qui VIT encore. Un
    collègue pose une région, puis l'importatrice la supprime ; il ne reste rien de lui."""
    region = _region(client, decor["planche"], COLLEGUE)
    assert _albums(client, IMPORTEUSE)[decor["erreur"]]["destructible"] is False
    assert client.delete(f"/api/regions/{region}", headers=IMPORTEUSE).status_code == 204
    assert _albums(client, IMPORTEUSE)[decor["erreur"]]["destructible"] is True


def test_ranger_ailleurs_n_est_pas_y_travailler_mais_ecrire_partout_reste_exige(client,
                                                                                decor):
    """Les mots de Hugo, et non la règle plus stricte de la maquette : rangée dans deux
    collections où l'importatrice écrit, la copie se supprime encore tout de suite — même
    rangée par un autre. Rangée dans une collection où elle n'écrit pas, elle se demande :
    la moitié AUTH-10 de la règle reste nécessaire."""
    aid = decor["erreur"]
    lien = f"/api/albums/{aid}/collections/{decor['incubateur']}"
    assert client.put(lien, headers=ADMIN).status_code == 201
    assert _albums(client, IMPORTEUSE)[aid]["destructible"] is True
    autre = _collection(client, "Autre")
    assert client.put(f"/api/albums/{aid}/collections/{autre}",
                      headers=ADMIN).status_code == 201
    assert _albums(client, IMPORTEUSE)[aid]["destructible"] is False
    assert client.delete(f"/api/albums/{aid}", headers=IMPORTEUSE).status_code == 403


def test_un_album_d_avant_le_fonds_se_demande(client, db_path, decor):
    """B3 — l'importateur d'un album d'avant la v30 n'a été écrit nulle part. Inconnu veut
    dire « demander » : seul un administrateur le détruit.

    Le décor rend l'album tel que la migration le laisse : depuis la v31, la règle lit QUI
    A CRÉÉ LA COPIE (`copie.creee_par`), que la migration recopie de l'importateur — NULL
    des deux côtés pour un album d'avant le fonds."""
    _sql(db_path, "UPDATE document SET importe_par = NULL")
    _sql(db_path, "UPDATE copie SET creee_par = NULL")
    aid = decor["erreur"]
    assert _albums(client, IMPORTEUSE)[aid]["destructible"] is False
    assert client.delete(f"/api/albums/{aid}", headers=IMPORTEUSE).status_code == 403
    assert _demander(client, aid, IMPORTEUSE).status_code == 201
    assert _albums(client, ADMIN)[aid]["destructible"] is True
    assert client.delete(f"/api/albums/{aid}", headers=ADMIN).status_code == 204


def test_un_compte_partage_ne_supprime_jamais_seul(client, decor):
    """R7 — « celui qui l'a importé » ne désigne personne sous un login partagé. Le même
    compte, déclaré partagé APRÈS l'import, perd le geste ; le compte ne perd aucun accès."""
    client.get("/api/moi", headers=ATELIER)                     # → miroir `utilisateur`
    aid = _album(client, "Par l'atelier", decor["principale"], ATELIER)
    assert _albums(client, ATELIER)[aid]["destructible"] is True
    r = client.patch("/api/comptes/atelier/nature", headers=ADMIN, json={"nature": "collectif"})
    assert r.status_code == 200, r.text
    vu = _albums(client, ATELIER)[aid]
    assert (vu["ecrivable"], vu["destructible"]) == (True, False)
    assert client.delete(f"/api/albums/{aid}", headers=ATELIER).status_code == 403


def test_le_refus_ne_dit_pas_laquelle_des_conditions_manque(client, db_path, decor):
    """Trois causes, un seul texte : dire « c'est un collègue qui y a travaillé » ou « une
    autre collection le porte » décrirait le corpus à qui ne le lit pas."""
    aid = decor["erreur"]
    pas_importee = client.delete(f"/api/albums/{aid}", headers=COLLEGUE)
    _region(client, decor["planche"], COLLEGUE)
    travaillee = client.delete(f"/api/albums/{aid}", headers=IMPORTEUSE)
    _sql(db_path, "DELETE FROM regions WHERE id <> ?", (decor["region"],))
    autre = _collection(client, "Autre")
    client.put(f"/api/albums/{aid}/collections/{autre}", headers=ADMIN)
    partagee = client.delete(f"/api/albums/{aid}", headers=IMPORTEUSE)
    assert pas_importee.status_code == travaillee.status_code == partagee.status_code == 403
    assert pas_importee.json() == travaillee.json() == partagee.json()
    assert "collegue" not in pas_importee.text and "Autre" not in pas_importee.text


def test_une_planche_suit_la_regle_du_document(client, decor):
    """B4 — on supprime une planche là où l'on pourrait supprimer le document, et nulle part
    ailleurs. Une planche n'a pas de demande à elle : le refus dit de s'adresser à un
    administrateur."""
    seconde = _planche(client, decor["erreur"], IMPORTEUSE)
    assert client.delete(f"/api/planches/{seconde}", headers=IMPORTEUSE).status_code == 204
    r = client.delete(f"/api/planches/{decor['planche']}", headers=COLLEGUE)
    assert r.status_code == 403 and "administrateur" in r.json()["detail"]
    assert client.delete(f"/api/planches/{decor['planche']}", headers=ADMIN).status_code == 204


def test_la_liste_dit_ce_que_devient_le_travail(client, decor):
    """`partage` : l'album vit AUSSI dans une collection que l'appelant ne lit pas — le
    supprimer de ses collections à lui ne l'enverrait donc pas au fonds. Ce que cela
    révèle est ce qu'AUTH-10 a accepté, et à qui : qu'un autre usage existe, jamais
    lequel, à qui ÉCRIT dans l'album. Une lectrice ne l'apprend pas (relecture croisée).
    Faux pour la portée totale, qui lit tout ; `au_fonds` est l'autre moitié."""
    aid = decor["erreur"]
    vus = {nom: _albums(client, qui)[aid] for nom, qui in
           (("importeuse", IMPORTEUSE), ("lectrice", LECTRICE), ("admin", ADMIN))}
    assert {n: (v["partage"], v["au_fonds"]) for n, v in vus.items()} == {
        "importeuse": (False, False), "lectrice": (False, False), "admin": (False, False)}
    assert client.put(f"/api/albums/{aid}/collections/{decor['incubateur']}",
                      headers=ADMIN).status_code == 201
    # Le collègue écrit dans Principale et ne lit pas l'Incubateur : il l'apprend. La
    # lectrice ne lit pas l'Incubateur non plus, mais n'écrit nulle part : elle ne
    # l'apprend pas. L'importatrice écrit dans les deux : rien à apprendre.
    assert _albums(client, COLLEGUE)[aid]["partage"] is True
    assert _albums(client, LECTRICE)[aid]["partage"] is False
    assert _albums(client, IMPORTEUSE)[aid]["partage"] is False
    assert _albums(client, ADMIN)[aid]["partage"] is False
    for a in _albums(client, ADMIN).values():
        assert isinstance(a["partage"], bool) and isinstance(a["au_fonds"], bool)


def test_qui_ne_lit_pas_l_album_recoit_toujours_un_404(client, decor):
    """La garde ne passe qu'APRÈS l'accesseur gardé en écriture."""
    assert client.delete(f"/api/albums/{decor['erreur']}", headers=LECTRICE).status_code == 404
    assert client.delete(f"/api/planches/{decor['planche']}",
                         headers=LECTRICE).status_code == 404


def test_la_clause_aux_extremites_et_ses_parametres_lies():
    assert autorisation.TOTALE.clause_suppression_directe("a.id") == ("1", [])
    # Sans login, personne n'a importé quoi que ce soit.
    assert autorisation.Portee(ecriture=frozenset({1})).clause_suppression_directe() \
        == ("0", [])
    assert autorisation.Portee(lecture=frozenset({1}),
                               utilisateur="x").clause_suppression_directe() == ("0", [])
    sql, params = autorisation.Portee(ecriture=frozenset({3}),
                                      utilisateur="o'brien").clause_suppression_directe("z.id")
    # Les RANGS de l'échelle des crans (v32, COL-3, tranche 3b) sont des constantes écrites
    # dans le SQL, pas des identifiants : retirés avant de chercher une collection en clair.
    sans_rangs = sql.replace(database.sql_rang_du_cran("_tco.cran"), "") \
        .replace(database.sql_rang_du_cran("_tco2.cran"), "")
    assert "o'brien" not in sql and "3" not in sans_rangs.replace("_t", "")
    # Six sources du travail d'autrui depuis la v32, plus le créateur et le compte partagé.
    assert sql.count("?") == len(params) and params.count("o'brien") == 8
    assert autorisation.TOTALE.peut_tenir_le_fonds() is True
    assert autorisation.Portee(admin=True, utilisateur="x").peut_tenir_le_fonds() is False


# =========================================================================== #
# Le fonds — supprimer de la collection, garder, rendre
# =========================================================================== #
def test_supprimer_de_sa_derniere_collection_garde_tout_au_fonds(client, db_path, decor):
    """La première réponse à « supprimer » ne détruit rien. L'album disparaît pour tous ceux
    qui le lisaient ; l'administrateur le voit au fonds, travail entier ; il le rend, et il
    revient chez eux tel qu'il était."""
    aid = decor["erreur"]
    _region(client, decor["planche"], COLLEGUE)
    lien = f"/api/albums/{aid}/collections/{decor['principale']}"
    assert client.delete(lien, headers=COLLEGUE).status_code == 204
    for qui in (IMPORTEUSE, COLLEGUE, LECTRICE):
        assert aid not in _albums(client, qui)
        assert client.get(f"/api/albums/{aid}/planches", headers=qui).status_code == 404
    vu = _albums(client, ADMIN)[aid]
    assert vu["au_fonds"] is True
    doc = next(d for d in client.get("/api/fonds", headers=ADMIN).json()["documents"]
               if d["copies"] and d["copies"][0]["album_id"] == aid)
    assert doc["appele"] is False and doc["copies"][0]["collections"] == []
    assert doc["copies"][0]["projet_id"] == _repli(db_path)
    assert doc["importe_par"] == "importeuse"
    assert _fichiers(decor["data"], aid), "garder au fonds n'efface pas les images"

    assert client.put(lien, headers=ADMIN).status_code == 201
    assert aid in _albums(client, LECTRICE)
    assert len(_sql(db_path, "SELECT r.id FROM regions r JOIN planches p "
                             "ON p.id = r.planche_id WHERE p.album_id = ?", (aid,))) == 2


def test_une_copie_gardee_ne_se_rend_qu_a_son_projet(client, db_path, decor):
    """Sortie de toute collection, la copie n'a plus de collection où lire son projet : il
    est ÉCRIT sur elle, et c'est lui que le rangement compare. Sans cela, un administrateur
    rendrait au fonds la copie d'un projet à une étude d'un autre."""
    pid = client.post("/api/projets", json={"nom": "Ailleurs"}, headers=ADMIN).json()["id"]
    ailleurs = _collection(client, "Étude ailleurs", pid)
    aid = decor["erreur"]
    assert client.delete(f"/api/albums/{aid}/collections/{decor['principale']}",
                         headers=IMPORTEUSE).status_code == 204
    r = client.put(f"/api/albums/{aid}/collections/{ailleurs}", headers=ADMIN)
    assert r.status_code == 409, r.text
    assert client.put(f"/api/albums/{aid}/collections/{decor['incubateur']}",
                      headers=ADMIN).status_code == 201


def test_une_copie_sans_projet_ecrit_prend_celui_qu_elle_quitte(client, db_path, decor):
    """Un album posé hors de tout chemin d'écriture n'a pas de projet écrit. Le sortir de
    sa dernière collection l'écrit d'abord — sans quoi la copie gardée entrerait ensuite
    dans n'importe quel projet."""
    aid = decor["erreur"]
    _sql(db_path, "UPDATE albums SET projet_id = NULL WHERE id = ?", (aid,))
    assert client.delete(f"/api/albums/{aid}/collections/{decor['principale']}",
                         headers=IMPORTEUSE).status_code == 204
    assert _sql(db_path, "SELECT projet_id FROM albums WHERE id = ?", (aid,)) \
        == [{"projet_id": _repli(db_path)}]


def test_une_copie_ne_change_jamais_de_projet_ecrit(client, db_path, decor):
    """Le projet ÉCRIT sur une copie ne se remplace pas, même quand ses collections en
    disent un autre — état interdit, qu'une base retouchée porte. La sortir d'une
    collection d'un autre projet ne lui donne pas ce projet-là."""
    pid = client.post("/api/projets", json={"nom": "Ailleurs"}, headers=ADMIN).json()["id"]
    ailleurs = _collection(client, "Étude ailleurs", pid)
    aid = decor["erreur"]
    _sql(db_path, "DELETE FROM collection_album WHERE album_id = ?", (aid,))
    _sql(db_path, "INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
         (ailleurs, aid))
    assert client.delete(f"/api/albums/{aid}/collections/{ailleurs}",
                         headers=ADMIN).status_code == 204
    assert _sql(db_path, "SELECT projet_id FROM albums WHERE id = ?", (aid,))         == [{"projet_id": _repli(db_path)}]


def test_importer_au_fonds_puis_rendre_a(client, db_path, decor):
    """« Importer au fonds » : l'album naît sans collection ni projet, appelé par personne.
    Rangé une première fois, il prend le projet de sa collection, et n'en change plus."""
    r = client.post("/api/albums", json={"titre": "Corpus à venir", "au_fonds": True},
                    headers=ADMIN)
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    assert r.json()["projet_id"] is None
    assert _sql(db_path, "SELECT 1 FROM collection_album WHERE album_id = ?", (aid,)) == []
    doc = _sql(db_path, "SELECT d.* FROM document d JOIN albums a ON a.document_id = d.id "
                        "WHERE a.id = ?", (aid,))[0]
    assert (doc["importe_par"], doc["projet_origine_id"]) == (ADMIN["Remote-User"], None)
    assert _sql(db_path, "SELECT cible_table, type FROM evenement WHERE cible_id = ? "
                         "AND cible_table IN ('document', 'collection_album')",
                (doc["id"],)) == [{"cible_table": "document", "type": "creation"}]
    fonds = {d["id"]: d for d in client.get("/api/fonds", headers=ADMIN).json()["documents"]}
    assert fonds[doc["id"]]["appele"] is False
    _planche(client, aid, ADMIN)

    pid = client.post("/api/projets", json={"nom": "Ailleurs"}, headers=ADMIN).json()["id"]
    ailleurs = _collection(client, "Étude ailleurs", pid)
    assert client.put(f"/api/albums/{aid}/collections/{ailleurs}",
                      headers=ADMIN).status_code == 201
    assert _sql(db_path, "SELECT projet_id FROM albums WHERE id = ?", (aid,)) \
        == [{"projet_id": pid}]
    assert client.put(f"/api/albums/{aid}/collections/{decor['principale']}",
                      headers=ADMIN).status_code == 409


def test_importer_au_fonds_est_reserve_et_ne_prend_pas_de_collection(client, decor):
    r = client.post("/api/albums", json={"titre": "X", "au_fonds": True}, headers=IMPORTEUSE)
    assert r.status_code == 403 and "administrateurs" in r.json()["detail"]
    r = client.post("/api/albums", headers=ADMIN, json={
        "titre": "X", "au_fonds": True, "collection_id": decor["principale"]})
    assert r.status_code == 422, r.text
    assert "X" not in {a["titre"] for a in _albums(client, ADMIN).values()}


def test_en_mono_poste_on_tient_le_fonds(client, db_path):
    r = client.post("/api/albums", json={"titre": "Seul au poste", "au_fonds": True})
    assert r.status_code == 201, r.text
    assert client.get("/api/fonds").status_code == 200
    assert client.get("/api/demandes").json() == []
    assert client.delete(f"/api/albums/{r.json()['id']}").status_code == 204


def test_supprimer_un_projet_dont_une_copie_est_gardee_au_fonds(client, db_path, decor):
    """Un projet ne se supprime que lorsqu'aucun album n'en est. Une copie gardée au fonds
    en est encore : le refus le dit, et la copie détruite, le projet part."""
    pid = client.post("/api/projets", json={"nom": "Éphémère"}, headers=ADMIN).json()["id"]
    cid = _collection(client, "Étude éphémère", pid)
    aid = _album(client, "Copie", cid, ADMIN)
    assert client.delete(f"/api/albums/{aid}/collections/{cid}",
                         headers=ADMIN).status_code == 204
    assert client.delete(f"/api/collections/{cid}", headers=ADMIN).status_code == 204
    r = client.delete(f"/api/projets/{pid}", headers=ADMIN)
    assert r.status_code == 409 and "1 album(s) de ce projet sont gardés au fonds"         in r.json()["detail"], r.text
    assert "rangé" not in r.json()["detail"]
    assert client.delete(f"/api/albums/{aid}", headers=ADMIN).status_code == 204
    assert client.delete(f"/api/projets/{pid}", headers=ADMIN).status_code == 204


def test_le_refus_dit_ou_sont_les_albums_qui_designent_encore_le_projet(client, db_path,
                                                                        decor):
    """Une copie qui désigne un projet sans être rangée dans l'une de ses collections est au
    fonds — ou, par une base retouchée, rangée dans la collection d'un AUTRE projet. Le
    refus disait « gardés au fonds » pour les deux : il les compte à part."""
    pid = client.post("/api/projets", json={"nom": "Éphémère"}, headers=ADMIN).json()["id"]
    _sql(db_path, "UPDATE albums SET projet_id = ? WHERE id = ?", (pid, decor["erreur"]))
    r = client.delete(f"/api/projets/{pid}", headers=ADMIN)
    assert r.status_code == 409, r.text
    assert "1 album(s) désignent ce projet en étant rangés dans la collection d'un autre"         in r.json()["detail"] and "fonds" not in r.json()["detail"]


# =========================================================================== #
# La demande — un document
# =========================================================================== #
def test_deposer_une_demande_et_qui_la_voit(client, db_path, decor):
    """R3 : le motif est obligatoire. Tous ceux qui lisent l'album voient QU'une suppression
    est demandée — jamais le motif, qui ne se lit que dans le fonds ; et le nom de qui
    demande, une lectrice ne le lit plus (Hugo, 2026-10-15 : la proposition R2 est
    renversée, cf. les tests de « Qui lit le nom de qui demande »)."""
    aid = decor["erreur"]
    r = _demander(client, aid, COLLEGUE, motif="Doublon de « Erreur bis »")
    assert r.status_code == 201, r.text
    d = r.json()
    assert (d["genre"], d["demandeur"], d["en_attente"]) == \
        ("suppression_document", "collegue", True)
    assert d["documents"][0]["album_id"] == aid and d["documents"][0]["titre"] == "Erreur"
    # Le projet de la copie, et son NOM au jour de la demande : l'identifiant d'un projet
    # se réattribue, et une demande répondue reste (relecture croisée, mutant M25).
    assert (d["projet_id"], d["projet_nom"]) == (_repli(db_path), database.NOM_PROJET_DEFAUT)
    assert _sql(db_path, "SELECT projet_nom FROM demande") == [
        {"projet_nom": database.NOM_PROJET_DEFAUT}]
    vu = _albums(client, LECTRICE)[aid]["demande"]
    assert vu is not None and "demandeur" not in vu and "motif" not in vu
    assert "Doublon" not in client.get("/api/albums", headers=LECTRICE).text
    assert _sql(db_path, "SELECT agent FROM evenement WHERE cible_table = 'demande' "
                         "AND type = 'creation'") == [{"agent": "collegue"}]
    assert aid in _albums(client, ADMIN), "demander n'efface rien"


@pytest.mark.parametrize("motif", ["", "   ", None])
def test_une_demande_sans_motif_est_refusee(client, decor, motif):
    r = client.post("/api/demandes", headers=COLLEGUE, json={
        "genre": "suppression_document", "album_id": decor["erreur"], "motif": motif})
    assert r.status_code == 422, r.text


def test_les_refus_d_une_demande_se_nomment(client, decor):
    aid = decor["erreur"]
    # Qui peut supprimer seul n'a rien à demander.
    r = _demander(client, aid, IMPORTEUSE)
    assert r.status_code == 409 and "vous-même" in r.json()["detail"]
    assert _demander(client, aid, COLLEGUE).status_code == 201
    # La même suppression, déjà demandée — sans dire par qui (Hugo, 2026-10-15).
    r = _demander(client, aid, ATELIER)
    assert r.status_code == 409 and "déjà demandée" in r.json()["detail"]
    r = client.post("/api/demandes", headers=COLLEGUE,
                    json={"genre": "autre", "album_id": aid, "motif": "x"})
    assert r.status_code == 422
    # Qui ne fait que lire, et un album qui n'existe pas : la même absence.
    assert _demander(client, aid, LECTRICE).status_code == 404
    assert _demander(client, 99999, COLLEGUE).status_code == 404


# --------------------------------------------------------------------------- #
# Qui lit le nom de qui demande (Hugo, 2026-10-15)
# --------------------------------------------------------------------------- #
# « Le nom de qui demande une suppression ne se lit que par une portée totale et par la
# personne elle-même. » Une question de cloisonnement : la ligne d'un album se lit par
# n'importe laquelle de ses collections, et le nom d'une personne de l'Incubateur ne doit
# pas arriver aux lectrices du corpus principal. Chaque identité est jouée, et l'on cherche
# le login ET le nom lisible dans la réponse ENTIÈRE, pas seulement sous la clé attendue.
NOM_COLLEGUE = "Camille Zzcollegue"


def _demande_de_la_collegue(client, decor):
    client.get("/api/moi", headers={**COLLEGUE, "Remote-Name": NOM_COLLEGUE})
    r = _demander(client, decor["erreur"], COLLEGUE)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_l_administrateur_et_la_personne_lisent_le_nom(client, decor):
    demande = _demande_de_la_collegue(client, decor)
    vu = _albums(client, ADMIN)[decor["erreur"]]["demande"]
    assert vu == {"id": demande, "date_creation": vu["date_creation"],
                  "demandeur": "collegue", "demandeur_nom": NOM_COLLEGUE}
    vu = _albums(client, COLLEGUE)[decor["erreur"]]["demande"]
    assert (vu["demandeur"], vu["demandeur_nom"]) == ("collegue", NOM_COLLEGUE)


@pytest.mark.parametrize("qui", [LECTRICE, ATELIER, IMPORTEUSE],
                         ids=["lectrice", "une autre qui ecrit", "l importatrice"])
def test_les_autres_lecteurs_voient_la_demande_sans_le_nom(client, decor, qui):
    """Une lectrice, une autre personne qui écrit dans la collection, et l'importatrice
    elle-même : chacune voit qu'une suppression est demandée, et rien de plus — ni la clé
    `demandeur`, ni le nom, nulle part dans la liste."""
    _demande_de_la_collegue(client, decor)
    rep = client.get("/api/albums", headers=qui)
    vu = {a["id"]: a for a in rep.json()}[decor["erreur"]]["demande"]
    assert vu is not None and set(vu) == {"id", "date_creation"}, vu
    assert "collegue" not in rep.text and "Zzcollegue" not in rep.text


def test_en_mono_poste_le_nom_se_lit(client, db_path):
    """Le mono-poste est une portée totale : rien à cloisonner, le nom se lit."""
    aid = client.post("/api/albums", json={"titre": "Seul"}).json()["id"]
    doc = _sql(db_path, "SELECT document_id FROM albums WHERE id = ?", (aid,))[0]["document_id"]
    _sql(db_path, "INSERT INTO demande (genre, demandeur, motif) "
                  "VALUES ('suppression_document', 'quelquun', 'x')")
    _sql(db_path, "INSERT INTO demande_document (demande_id, document_id, album_id, titre) "
                  "VALUES (1, ?, ?, 'Seul')", (doc, aid))
    vu = {a["id"]: a for a in client.get("/api/albums").json()}[aid]["demande"]
    assert vu["demandeur"] == "quelquun"


def test_le_refus_du_doublon_ne_nomme_que_soi(client, decor):
    """Le 409 « déjà demandée » est une autre porte vers le même nom : il le dit à qui a
    demandé (« par vous »), et à personne d'autre."""
    _demande_de_la_collegue(client, decor)
    r = _demander(client, decor["erreur"], ATELIER)
    assert r.status_code == 409, r.text
    assert r.json()["detail"].startswith("Cette suppression est déjà demandée, depuis le ")
    assert "collegue" not in r.text and "Zzcollegue" not in r.text
    r = _demander(client, decor["erreur"], COLLEGUE)
    assert r.status_code == 409, r.text
    assert r.json()["detail"].startswith("Cette suppression est déjà demandée, par vous le ")


def test_peut_nommer_le_demandeur_aux_extremites():
    """La question elle-même : une portée totale nomme tout le monde ; un compte se nomme
    lui-même et personne d'autre ; sans login, personne — pas même une demande sans
    demandeur, que `None == None` laisserait passer."""
    total = autorisation.Portee(tout=True, admin=True)
    moi = autorisation.Portee(utilisateur="sam", lecture=frozenset({1}))
    anonyme = autorisation.Portee(lecture=frozenset({1}))
    assert total.peut_nommer_le_demandeur("sam") and total.peut_nommer_le_demandeur(None)
    assert moi.peut_nommer_le_demandeur("sam")
    assert not moi.peut_nommer_le_demandeur("lia")
    assert not moi.peut_nommer_le_demandeur(None)
    assert not anonyme.peut_nommer_le_demandeur(None)


# --------------------------------------------------------------------------- #
# La certification (Hugo, 2026-10-15)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("certifie", [False, None, "non"])
def test_une_demande_sans_certification_est_refusee(client, db_path, decor, certifie):
    """La case est exigée par le SERVEUR aussi : un écran qui l'oublierait, ou un appel
    sans écran, ne la contourne pas. Rien n'est écrit."""
    corps = {"genre": "suppression_document", "album_id": decor["erreur"],
             "motif": "Doublon"}
    if certifie is not None:
        corps["certifie"] = certifie
    r = client.post("/api/demandes", headers=COLLEGUE, json=corps)
    assert r.status_code == 422, r.text
    if certifie != "non":                    # « non » n'est pas un booléen : 422 de forme
        assert r.json()["detail"].startswith("Cochez la certification"), r.text
    assert _sql(db_path, "SELECT 1 FROM demande") == []
    assert _sql(db_path, "SELECT 1 FROM evenement WHERE cible_table = 'demande'") == []


def test_la_certification_est_ecrite_et_lue_par_l_administrateur(client, db_path, decor):
    r = _demander(client, decor["erreur"], COLLEGUE)
    assert r.status_code == 201, r.text
    ligne = _sql(db_path, "SELECT certifie_le, date_creation FROM demande")[0]
    assert ligne["certifie_le"] and ligne["certifie_le"] == ligne["date_creation"]
    vue = client.get("/api/demandes", headers=ADMIN).json()[0]
    assert (vue["demandeur"], vue["certifie_le"]) == ("collegue", ligne["certifie_le"])
    fonds = {d["id"]: d for d in client.get("/api/fonds", headers=ADMIN).json()["documents"]}
    doc = _sql(db_path, "SELECT document_id FROM albums WHERE id = ?",
               (decor["erreur"],))[0]["document_id"]
    assert fonds[doc]["demande"]["certifie_le"] == ligne["certifie_le"]


def test_un_projet_se_demande_sans_certification(client, db_path, projet):
    """Un projet ne se supprime que vide : il n'y a pas de données à certifier."""
    r = _demander_projet(client, projet, IMPORTEUSE)
    assert r.status_code == 201, r.text
    assert r.json()["certifie_le"] is None


# --------------------------------------------------------------------------- #
# Ce que les autres ont fait, sous la demande (Hugo, 2026-10-15)
# --------------------------------------------------------------------------- #
def _detail(client, demande_id):
    vues = {d["id"]: d for d in client.get("/api/demandes", headers=ADMIN).json()}
    return vues[demande_id]["documents"][0]


def test_l_administrateur_voit_qui_d_autre_y_a_travaille(client, db_path, decor):
    """Qui (login, nom), combien de gestes de chaque sorte, et la date du dernier. Le
    demandeur n'y est pas, même s'il a travaillé ; l'importatrice y est, comme tout autre ;
    un attribut dont l'auteur n'est pas écrit y est sous un agent inconnu."""
    client.get("/api/moi", headers={**COLLEGUE, "Remote-Name": "Camille Zzcollegue"})
    r2 = _region(client, decor["planche"], COLLEGUE)
    assert client.put(f"/api/regions/{r2}/annotation", headers=COLLEGUE,
                      json={"note": "vu", "tags": []}).status_code == 200
    _locuteur(client, decor)
    _region(client, decor["planche"], ATELIER)               # le demandeur aussi travaille
    vid = _valeur_de_case(client)
    _sql(db_path, "INSERT INTO region_attribut (region_id, valeur_id) VALUES (?, ?)",
         (decor["region"], vid))
    demande = _demander(client, decor["erreur"], ATELIER).json()["id"]
    # Les gestes de l'importatrice vieillis à la main, sauf son scan : « le dernier » est le
    # plus récent de TOUS, y compris dans une sorte qui en compte deux (la naissance du
    # document, vieillie, et son scan).
    _sql(db_path, "UPDATE evenement SET date = '2020-01-01 00:00:00' WHERE agent = 'importeuse' "
                  "AND (cible_table = 'regions' OR (cible_table = 'document' "
                  "AND type = 'creation'))")
    scan = _sql(db_path, "SELECT date FROM evenement WHERE agent = 'importeuse' AND "
                         "cible_table = 'document' AND type = 'modification'")
    assert len(scan) == 1 and scan[0]["date"] > "2020-01-01 00:00:00"

    x = _detail(client, demande)
    assert x["importe_par"] == "importeuse"
    par = {e["agent"]: e for e in x["travail_des_autres"]}
    assert set(par) == {"collegue", "importeuse", None}, par
    assert par["collegue"]["agent_nom"] == "Camille Zzcollegue"
    assert par["collegue"]["gestes"] == {"regions": 1, "annotations": 1, "bulle_locuteur": 1}
    derniere = _sql(db_path, "SELECT MAX(date) AS d FROM evenement WHERE agent = 'collegue' "
                             "AND agent_type = 'humain' AND cible_table IN "
                             "('regions', 'annotations', 'bulle_locuteur')")[0]["d"]
    assert par["collegue"]["dernier"] == derniere
    # L'importatrice : sa région, la naissance du document et le scan qu'elle a ajouté.
    assert par["importeuse"]["gestes"] == {"regions": 1, "document": 2}  # naissance, scan
    assert par["importeuse"]["dernier"] == scan[0]["date"]
    assert par[None] == {"agent": None, "agent_nom": None, "dernier": None,
                         "collectif": False, "gestes": {"region_attribut": 1}}
    # Le plus récent d'abord, l'inconnu sans date en dernier.
    assert [e["agent"] for e in x["travail_des_autres"]][-1] is None


def test_un_document_d_avant_le_fonds_dit_ce_qu_on_sait(client, db_path, decor):
    """L'importateur n'est écrit nulle part : `importe_par` est vide, et le travail de
    tous, l'ancienne importatrice comprise, est celui d'« autres »."""
    _sql(db_path, "UPDATE document SET importe_par = NULL")
    demande = _demander(client, decor["erreur"], COLLEGUE).json()["id"]
    x = _detail(client, demande)
    assert x["importe_par"] is None and x["importe_par_nom"] is None
    assert [e["agent"] for e in x["travail_des_autres"]] == ["importeuse"]


def test_une_demande_sans_demandeur_garde_les_gestes_sans_auteur(client, db_path, decor):
    """`demande.demandeur` est nullable — une demande venue un jour de quelqu'un sans
    compte. Un geste dont l'auteur n'est pas écrit n'est pas le sien pour autant : il reste
    dans le détail, avec ceux de l'importatrice."""
    vid = _valeur_de_case(client)
    _sql(db_path, "INSERT INTO region_attribut (region_id, valeur_id) VALUES (?, ?)",
         (decor["region"], vid))
    doc = _sql(db_path, "SELECT document_id FROM albums WHERE id = ?",
               (decor["erreur"],))[0]["document_id"]
    _sql(db_path, "INSERT INTO demande (genre, demandeur, motif) "
                  "VALUES ('suppression_document', NULL, 'x')")
    _sql(db_path, "INSERT INTO demande_document (demande_id, document_id, album_id, titre) "
                  "VALUES (1, ?, ?, 'Erreur')", (doc, decor["erreur"]))
    agents = {e["agent"] for e in _detail(client, 1)["travail_des_autres"]}
    assert agents == {"importeuse", None}, agents


def test_personne_d_autre(client, decor):
    """Le demandeur seul — un compte partagé, qui a importé, ne supprime jamais seul : la
    liste est vide. Son propre import n'y compte pas."""
    client.get("/api/moi", headers=ATELIER)
    aid = _album(client, "Par l'atelier", decor["principale"], ATELIER)
    _region(client, _planche(client, aid, ATELIER), ATELIER)
    assert client.patch("/api/comptes/atelier/nature", headers=ADMIN,
                        json={"nature": "collectif"}).status_code == 200
    r = _demander(client, aid, ATELIER)
    assert r.status_code == 201, r.text
    x = _detail(client, r.json()["id"])
    assert (x["importe_par"], x["travail_des_autres"]) == ("atelier", [])
    # … mais « personne d'autre » ne veut rien dire derrière un compte partagé : le détail
    # le dit, pour que l'écran le dise (relecture croisée). La règle, elle, ne change pas.
    assert x["demandeur_collectif"] is True


def test_le_detail_dit_quels_comptes_sont_partages(client, decor):
    """Un compte partagé parmi ceux qui ont travaillé se dit aussi, ligne par ligne ; un
    compte nominatif, non. Le demandeur nominatif n'est pas marqué."""
    _region(client, decor["planche"], COLLEGUE)
    client.get("/api/moi", headers=COLLEGUE)                    # → miroir `utilisateur`
    assert client.patch("/api/comptes/collegue/nature", headers=ADMIN,
                        json={"nature": "collectif"}).status_code == 200
    demande = _demander(client, decor["erreur"], ATELIER).json()["id"]
    x = _detail(client, demande)
    assert x["demandeur_collectif"] is False
    par = {e["agent"]: e["collectif"] for e in x["travail_des_autres"]}
    assert par == {"collegue": True, "importeuse": False}, par


@pytest.mark.parametrize("travail", sorted(TRAVAUX))
def test_le_detail_lit_ce_que_la_regle_lit(client, decor, travail):
    """La règle et le détail partagent leurs sources (`autorisation._sources_du_travail`) :
    chaque travail d'un autre qui fait DEMANDER l'importatrice apparaît sous sa demande,
    au nom de qui l'a fait ou d'un auteur inconnu."""
    TRAVAUX[travail](client, decor)
    assert _albums(client, IMPORTEUSE)[decor["erreur"]]["destructible"] is False
    demande = _demander(client, decor["erreur"], IMPORTEUSE)
    assert demande.status_code == 201, demande.text
    agents = {e["agent"] for e in _detail(client, demande.json()["id"])["travail_des_autres"]}
    assert agents and agents <= {"collegue", None}, agents


def test_le_detail_ne_sort_que_vers_qui_tient_le_fonds(client, decor):
    """Il nomme des comptes : la réponse rendue à qui dépose n'en porte rien, et une
    demande répondue ne le recalcule plus."""
    _region(client, decor["planche"], COLLEGUE)
    r = _demander(client, decor["erreur"], ATELIER)
    assert r.status_code == 201, r.text
    assert "travail_des_autres" not in r.json()["documents"][0]
    assert "collegue" not in r.text and "importeuse" not in r.text
    _repondre(client, r.json()["id"], "refusee")
    assert "travail_des_autres" not in _detail(client, r.json()["id"])


def test_garder_clot_la_demande_qu_on_peut_redeposer(client, db_path, decor):
    """R4 — « garder » : la demande reste, close ; l'album est intact et sa ligne ne porte
    plus de demande ; on peut redemander, et l'administrateur voit le refus antérieur."""
    aid = decor["erreur"]
    premiere = _demander(client, aid, COLLEGUE).json()["id"]
    r = _repondre(client, premiere, "refusee")
    assert r.status_code == 200, r.text
    assert (r.json()["reponse"], r.json()["repondu_par"]) == ("refusee", "decor")
    assert _albums(client, LECTRICE)[aid]["demande"] is None
    assert _fichiers(decor["data"], aid)
    assert _repondre(client, premiere, "acceptee").status_code == 409
    seconde = _demander(client, aid, COLLEGUE)
    assert seconde.status_code == 201
    demandes = {d["id"]: d for d in client.get("/api/demandes", headers=ADMIN).json()}
    assert demandes[seconde.json()["id"]]["refus_anterieurs"] == 1
    assert demandes[premiere]["en_attente"] is False


def test_accepter_detruit_le_document_et_ses_images(client, db_path, decor):
    aid = decor["erreur"]
    _region(client, decor["planche"], COLLEGUE)
    doc = _sql(db_path, "SELECT document_id FROM albums WHERE id = ?", (aid,))[0]["document_id"]
    demande = _demander(client, aid, COLLEGUE).json()["id"]
    r = _repondre(client, demande, "acceptee")
    assert r.status_code == 200, r.text
    assert r.json()["reponse"] == "acceptee" and r.json()["documents"][0]["copie"] is None
    assert aid not in _albums(client, ADMIN)
    assert _sql(db_path, "SELECT 1 FROM document WHERE id = ?", (doc,)) == []
    assert _fichiers(decor["data"], aid) == []
    assert _sql(db_path, "SELECT agent FROM evenement WHERE cible_table = 'document' "
                         "AND type = 'suppression'") == [{"agent": "decor"}]


def test_l_importatrice_qui_detruit_satisfait_la_demande_d_un_autre(client, db_path, decor):
    """La demande d'un collègue n'est pas un travail : elle n'ôte pas à l'importatrice le
    geste direct. Détruire clôt la demande, et dit qui y a répondu."""
    demande = _demander(client, decor["erreur"], COLLEGUE).json()["id"]
    assert client.delete(f"/api/albums/{decor['erreur']}", headers=IMPORTEUSE).status_code == 204
    assert _sql(db_path, "SELECT reponse, repondu_par FROM demande WHERE id = ?",
                (demande,)) == [{"reponse": "acceptee", "repondu_par": "importeuse"}]


@pytest.mark.parametrize("geste", ["fonds", "demandes", "reponse"])
def test_le_fonds_refuse_sur_le_droit_avant_de_chercher(client, decor, geste):
    """Le même 403, que l'objet existe ou non : il parle du droit de l'appelant. Le
    propriétaire d'une collection, un responsable de projet, un compte qui écrit : aucun
    ne tient le fonds."""
    demande = _demander(client, decor["erreur"], COLLEGUE).json()["id"]
    reponses = []
    for ident in (demande, 99999):
        if geste == "fonds":
            reponses.append(client.get("/api/fonds", headers=IMPORTEUSE))
        elif geste == "demandes":
            reponses.append(client.get("/api/demandes", headers=IMPORTEUSE))
        else:
            reponses.append(_repondre(client, ident, "acceptee", qui=IMPORTEUSE))
    assert [r.status_code for r in reponses] == [403, 403]
    assert reponses[0].json() == reponses[1].json()
    assert decor["erreur"] in _albums(client, ADMIN)
    assert _repondre(client, 99999, "acceptee").status_code == 404
    assert _repondre(client, demande, "detruire").status_code == 422


# =========================================================================== #
# La demande — un projet (B5)
# =========================================================================== #
@pytest.fixture
def projet(client, decor):
    pid = client.post("/api/projets", json={"nom": "Séminaire"}, headers=ADMIN).json()["id"]
    for principal, role in (("importeuse", "responsable"), ("collegue", "membre")):
        r = client.put(f"/api/projets/{pid}/membres", headers=ADMIN,
                       json={"genre": "utilisateur", "principal": principal, "role": role})
        assert r.status_code == 200, r.text
    return pid


def _demander_projet(client, pid, qui, motif="Le séminaire est fini"):
    return client.post("/api/demandes", headers=qui, json={
        "genre": "suppression_projet", "projet_id": pid, "motif": motif})


def test_le_responsable_demande_la_suppression_de_son_projet(client, db_path, projet):
    r = _demander_projet(client, projet, IMPORTEUSE)
    assert r.status_code == 201, r.text
    assert (r.json()["projet_id"], r.json()["projet_nom"]) == (projet, "Séminaire")
    vus = {p["id"]: p for p in client.get("/api/projets", headers=IMPORTEUSE).json()}
    assert vus[projet]["demande_suppression"]["id"] == r.json()["id"]
    # Un simple membre ne gère pas : ni la clé, ni le geste.
    vus = {p["id"]: p for p in client.get("/api/projets", headers=COLLEGUE).json()}
    assert "demande_suppression" not in vus[projet]
    r = _demander_projet(client, projet, COLLEGUE)
    assert r.status_code == 403 and "responsable" in r.json()["detail"]
    assert _demander_projet(client, projet, LECTRICE).status_code == 404
    assert _demander_projet(client, projet, IMPORTEUSE).status_code == 409
    r = _demander_projet(client, projet, ADMIN)
    assert r.status_code == 409 and "vous-même" in r.json()["detail"]


def test_un_second_responsable_ne_lit_pas_qui_a_demande(client, projet):
    """Le même refus du doublon, sur un projet : un second responsable apprend que la
    suppression est demandée, pas par qui."""
    r = client.put(f"/api/projets/{projet}/membres", headers=ADMIN,
                   json={"genre": "utilisateur", "principal": "atelier",
                         "role": "responsable"})
    assert r.status_code == 200, r.text
    assert _demander_projet(client, projet, IMPORTEUSE).status_code == 201
    r = _demander_projet(client, projet, ATELIER)
    assert r.status_code == 409, r.text
    assert "depuis le" in r.json()["detail"] and "importeuse" not in r.text
    r = _demander_projet(client, projet, IMPORTEUSE)
    assert r.status_code == 409 and "par vous" in r.json()["detail"], r.text


def test_le_projet_de_repli_ne_se_demande_pas(client, db_path, projet):
    repli = _repli(db_path)
    client.put(f"/api/projets/{repli}/membres", headers=ADMIN,
               json={"genre": "utilisateur", "principal": "importeuse", "role": "responsable"})
    r = _demander_projet(client, repli, IMPORTEUSE)
    assert r.status_code == 409 and "repli" in r.json()["detail"]


def test_accepter_la_suppression_d_un_projet_suit_ses_refus(client, db_path, projet):
    """Un projet n'est supprimé que vide : accepter une demande sur un projet qui porte une
    collection répond le 409 de la suppression, et la demande reste en attente."""
    cid = _collection(client, "Une étude", projet)
    demande = _demander_projet(client, projet, IMPORTEUSE).json()["id"]
    r = _repondre(client, demande, "acceptee")
    assert r.status_code == 409 and "collection(s)" in r.json()["detail"]
    assert _sql(db_path, "SELECT reponse FROM demande WHERE id = ?", (demande,)) \
        == [{"reponse": None}]
    assert client.delete(f"/api/collections/{cid}", headers=ADMIN).status_code == 204
    r = _repondre(client, demande, "acceptee")
    assert r.status_code == 200 and r.json()["reponse"] == "acceptee", r.text
    assert _sql(db_path, "SELECT 1 FROM projet WHERE id = ?", (projet,)) == []
    # La demande garde le NOM du projet supprimé.
    assert r.json()["projet_nom"] == "Séminaire"


def test_supprimer_le_projet_directement_clot_sa_demande(client, db_path, projet):
    demande = _demander_projet(client, projet, IMPORTEUSE).json()["id"]
    assert client.delete(f"/api/projets/{projet}", headers=ADMIN).status_code == 204
    assert _sql(db_path, "SELECT reponse FROM demande WHERE id = ?", (demande,)) \
        == [{"reponse": "acceptee"}]


# =========================================================================== #
# « À regarder », les comptes, et ce qui sort
# =========================================================================== #
def test_une_demande_en_attente_est_a_regarder(client, decor):
    """La demande se lit dans « À regarder », en tête. Sa clé est `demande`, jamais
    `login` : l'écran mène tout signal qui porte un login à la fiche d'un compte."""
    demande = _demander(client, decor["erreur"], COLLEGUE).json()["id"]
    lignes = client.get("/api/comptes-et-groupes", headers=ADMIN).json()["a_regarder"]
    assert lignes[0] == {"signal": "demande_en_attente", "demande": demande,
                         "genre": "suppression_document"}
    assert comptes.ORDRE_SIGNAUX[0] == "demande_en_attente"
    _repondre(client, demande, "refusee")
    lignes = client.get("/api/comptes-et-groupes", headers=ADMIN).json()["a_regarder"]
    assert not [l for l in lignes if l["signal"] == "demande_en_attente"]


def test_demander_n_est_pas_du_travail_laisse(client, db_path, decor):
    """Déposer une demande n'orpheline aucune annotation : le verdict de départ d'un compte
    ne bouge pas, et la demande ne lui donne pas de rang dans les pseudonymes de sortie."""
    import _commun

    def conn():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        return c

    avant = comptes.traces(conn())[0]
    rangs = _commun.pseudonymes(conn())
    demande = _demander(client, decor["erreur"], COLLEGUE).json()["id"]
    _repondre(client, demande, "refusee")
    assert _sql(db_path, "SELECT agent FROM evenement WHERE cible_table = 'demande' "
                         "ORDER BY id") == [{"agent": "collegue"}, {"agent": "decor"}],         "le semis ne pose pas ce qu'on cherche"
    assert comptes.traces(conn())[0] == avant
    assert _commun.pseudonymes(conn()) == rangs
    assert "collegue" not in rangs


def test_rien_d_une_demande_ne_sort_d_aucun_artefact(client, db_path, tmp_path, decor):
    """Ni qui demande, ni pourquoi, ni les actes de la demande ne partent par les exports
    d'album, la voie du dépôt ou les outils. Le semis est son propre témoin."""
    aid = decor["erreur"]
    client.patch(f"/api/collections/{decor['principale']}", headers=ADMIN,
                 json={"statut_diffusion": "public"})
    client.get("/api/moi", headers={"Remote-User": "zzdemande7", "Remote-Name": "Zzqui7"})
    _accorder(client, decor["principale"], "zzdemande7", "ecriture")
    qui = {"Remote-User": "zzdemande7"}
    demande = _demander(client, aid, qui, motif="ZZMOTIF7").json()["id"]
    temoin = json.dumps(client.get("/api/demandes", headers=ADMIN).json(),
                        ensure_ascii=False) + client.get("/api/albums", headers=ADMIN).text
    assert all(m in temoin for m in ("zzdemande7", "Zzqui7", "ZZMOTIF7")), \
        "le semis ne pose pas ce qu'on cherche"
    _repondre(client, demande, "refusee")

    cid = decor["principale"]
    sorties = {}
    for chemin in (f"/api/export/json?album_id={aid}", f"/api/export/csv?album_id={aid}",
                   f"/api/export/tei?album_id={aid}",
                   f"/api/collections/{cid}/depot/description",
                   f"/api/collections/{cid}/depot/metadonnees?format=zip",
                   f"/api/collections/{cid}/depot/iiif?base_url=https://images.example.org"):
        r = client.get(chemin, headers=ADMIN)
        assert r.status_code == 200, (chemin, r.text[:300])
        sorties[chemin] = _fouillable(r.content)
    for outil, args, produits in (
            ("metadonnees_collection.py", ["--json", "-"], []),
            ("provenance_export.py", ["--out-dir", str(tmp_path / "prov")],
             [tmp_path / "prov"]),
            ("crosswalk_depot.py", ["--out-dir", str(tmp_path / "cw")], [tmp_path / "cw"])):
        code, out, err = _outil(db_path, outil, *args)
        assert code == 0, (outil, err[-600:])
        fichiers = [f for d in produits for f in d.glob("**/*") if f.is_file()]
        sorties[f"{outil} {args[0]}"] = out + err + "\n".join(
            _fouillable(f.read_bytes()) for f in fichiers)
    for surface, texte in sorties.items():
        assert len(texte) > 40, f"{surface} : sortie vide, le contrôle ne mesure rien"
        for interdit in ("zzdemande7", "Zzqui7", "ZZMOTIF7", "suppression_document"):
            assert interdit not in texte, f"{surface} laisse sortir « {interdit} »"


# =========================================================================== #
# L'outil en ligne de commande suit la route
# =========================================================================== #
def test_l_outil_retire_un_album_de_sa_derniere_collection(client, db_path, decor):
    """Comme la route : retirée de sa dernière collection, la copie est gardée au fonds
    et emporte son projet — écrit d'abord, s'il ne l'était pas encore."""
    aid = decor["erreur"]
    _sql(db_path, "UPDATE albums SET projet_id = NULL WHERE id = ?", (aid,))
    code, _, err = _outil(db_path, "gerer_collections.py", "retirer",
                          str(decor["principale"]), "--albums", str(aid))
    assert code == 0, err
    assert _sql(db_path, "SELECT 1 FROM collection_album WHERE album_id = ?", (aid,)) == []
    assert _albums(client, ADMIN)[aid]["au_fonds"] is True
    assert _sql(db_path, "SELECT projet_id FROM albums WHERE id = ?", (aid,))         == [{"projet_id": _repli(db_path)}]
    assert _sql(db_path, "SELECT type FROM evenement WHERE cible_table = 'collection_album' "
                         "ORDER BY id DESC LIMIT 1") == [{"type": "delien"}]


# =========================================================================== #
# La garde se lit sous le verrou d'écriture (relecture croisée, sonde S9)
# =========================================================================== #
# Chaque test glisse une écriture CONCURRENTE — une seconde connexion, comme une seconde
# requête — entre la garde et le geste qu'elle autorise. Sous le verrou (`BEGIN IMMEDIATE`)
# elle ne peut pas passer : la base répond « verrouillée ». Sans lui, elle passait, et un
# travail validé après la garde partait avec l'album, ou une seconde réponse s'ajoutait.
def _ecrire_a_cote(db_path, sql, params=()):
    autre = sqlite3.connect(db_path, timeout=0.2)
    try:
        autre.execute(sql, params)
        autre.commit()
        return "écrite"
    except sqlite3.OperationalError as e:
        return "verrouillée" if "locked" in str(e) else str(e)
    finally:
        autre.close()


def _au_milieu(monkeypatch, module, nom, db_path, sql, params, vu):
    vraie = getattr(module, nom)

    def entre(*args, **kwargs):
        if not vu:
            vu.append(_ecrire_a_cote(db_path, sql, params))
        return vraie(*args, **kwargs)

    monkeypatch.setattr(module, nom, entre)


def test_un_travail_ne_se_glisse_pas_entre_la_garde_et_la_destruction(client, db_path, decor,
                                                                       monkeypatch):
    vu = []
    _au_milieu(monkeypatch, socle, "unindex_region", db_path,
               "INSERT INTO evenement (type, agent, agent_type, cible_table, cible_id) "
               "VALUES ('creation', 'collegue', 'humain', 'annotations', ?)",
               (decor["region"],), vu)
    assert client.delete(f"/api/albums/{decor['erreur']}", headers=IMPORTEUSE).status_code == 204
    assert vu == ["verrouillée"]


def test_ni_entre_la_garde_et_la_suppression_d_une_planche(client, db_path, decor,
                                                           monkeypatch):
    vu = []
    _au_milieu(monkeypatch, main, "unindex_region", db_path,
               "INSERT INTO evenement (type, agent, agent_type, cible_table, cible_id) "
               "VALUES ('creation', 'collegue', 'humain', 'annotations', ?)",
               (decor["region"],), vu)
    assert client.delete(f"/api/planches/{decor['planche']}", headers=IMPORTEUSE).status_code == 204
    assert vu == ["verrouillée"]


def test_deux_reponses_a_la_meme_demande_ne_passent_pas_ensemble(client, db_path, decor,
                                                                monkeypatch):
    from routes import fonds
    demande = _demander(client, decor["erreur"], COLLEGUE).json()["id"]
    vu = []
    _au_milieu(monkeypatch, fonds, "_clore_demandes", db_path,
               "UPDATE demande SET reponse = 'acceptee', repondu_par = 'autre' WHERE id = ?",
               (demande,), vu)
    assert _repondre(client, demande, "refusee").status_code == 200
    assert vu == ["verrouillée"]
    assert _sql(db_path, "SELECT reponse, repondu_par FROM demande WHERE id = ?",
                (demande,)) == [{"reponse": "refusee", "repondu_par": "decor"}]


def test_deux_demandes_du_meme_document_ne_passent_pas_ensemble(client, db_path, decor,
                                                                monkeypatch):
    from routes import fonds
    vu = []
    _au_milieu(monkeypatch, fonds, "_en_attente", db_path,
               "INSERT INTO demande (genre, demandeur, motif) "
               "VALUES ('suppression_document', 'autre', 'x')", (), vu)
    assert _demander(client, decor["erreur"], COLLEGUE).status_code == 201
    assert vu == ["verrouillée"]


def test_une_reponse_deja_donnee_ne_s_ecrit_pas_une_seconde_fois(client, db_path, decor):
    """La ligne de journal suivait l'`UPDATE` même quand il ne changeait rien."""
    demande = _demander(client, decor["erreur"], COLLEGUE).json()["id"]
    assert _repondre(client, demande, "refusee").status_code == 200
    avant = _sql(db_path, "SELECT COUNT(*) n FROM evenement WHERE cible_table = 'demande'")
    conn = database.get_connection()
    try:
        socle._clore_demandes(conn, autorisation.TOTALE, [demande], "acceptee")
        conn.commit()
    finally:
        conn.close()
    assert _sql(db_path, "SELECT COUNT(*) n FROM evenement WHERE cible_table = 'demande'")         == avant
    assert _sql(db_path, "SELECT reponse FROM demande WHERE id = ?", (demande,))         == [{"reponse": "refusee"}]
