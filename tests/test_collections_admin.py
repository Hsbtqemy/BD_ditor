"""AUTH-3 — administrer une collection : posséder, partager, ranger.

AUTH-2 avait fait le cloisonnement mais pas son administration : `collection_acces` ne se
remplissait qu'en SQL à la main. Ces tests portent sur le troisième palier — POSSÉDER, qui
ne découle pas d'écrire — et sur les deux invariants que le chantier ne doit jamais casser :
jamais zéro propriétaire, jamais un album sans collection.
"""
import sqlite3

import pytest

from conftest import ADMIN


# --------------------------------------------------------------------------- #
# Outils de décor
# --------------------------------------------------------------------------- #
def _acces(db_path, collection_id, principal, niveau, genre="utilisateur"):
    """Pose un accès directement en base (le décor, pas le geste testé)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT OR REPLACE INTO collection_acces "
                     "(collection_id, genre, principal, niveau) VALUES (?, ?, ?, ?)",
                     (collection_id, genre, principal, niveau))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def collection_a_alice(client, db_path, derriere_proxy):
    """Une collection créée PAR alice, qui en est donc propriétaire — par la route, pas
    par du SQL : c'est précisément ce qu'AUTH-3 ajoute."""
    r = client.post("/api/collections", json={"nom": "Corpus colonial"},
                    headers={"Remote-User": "alice"})
    assert r.status_code == 201
    return r.json()


# --------------------------------------------------------------------------- #
# Propriété
# --------------------------------------------------------------------------- #
def test_creer_une_collection_rend_proprietaire(collection_a_alice):
    """Le geste fondateur du chantier : ouvrir un espace de travail sans accès shell.

    Aucun droit préalable n'est demandé — refuser la création à qui n'a encore rien
    rendrait l'application inutilisable au premier jour de chacun.
    """
    assert collection_a_alice["acces"] == [
        {"genre": "utilisateur", "principal": "alice", "niveau": "proprietaire",
         "date_creation": collection_a_alice["acces"][0]["date_creation"]}]


def test_proprietaire_implique_ecriture_et_lecture(client, collection_a_alice):
    """Les niveaux s'empilent, et le cumul est fait DANS `Portee` — une seule fois. Un
    `in portee.ecriture` qui oublierait les propriétaires serait un refus silencieux et
    parfaitement crédible."""
    cid = collection_a_alice["id"]
    h = {"Remote-User": "alice"}
    vues = client.get("/api/collections", headers=h).json()
    mienne = next(c for c in vues if c["id"] == cid)
    assert mienne["mon_niveau"] == "proprietaire" and mienne["administrable"]
    # Le droit d'écriture suit : alice peut créer un album dans SA collection.
    r = client.post("/api/albums", json={"titre": "Le Lotus bleu", "collection_id": cid},
                    headers=h)
    assert r.status_code == 201


def test_ecrire_ne_donne_pas_le_droit_de_partager(client, db_path, collection_a_alice):
    """LE point du chantier. Écrire, c'est annoter ; posséder, c'est décider qui d'autre
    entrera. Sans cette séparation, le cercle s'élargirait sans que le propriétaire le
    sache, et un accès accordé par erreur deviendrait intraçable.

    Le refus est un 403 et non un 404 : bob VOIT la collection, il y travaille — un
    « introuvable » mentirait. C'est la même distinction qu'AUTH-2 fait pour un terme.
    """
    cid = collection_a_alice["id"]
    _acces(db_path, cid, "bob", "ecriture")
    h = {"Remote-User": "bob"}
    assert client.get("/api/collections/%d/acces" % cid, headers=h).status_code == 403
    assert client.put(f"/api/collections/{cid}/acces", headers=h,
                      json={"principal": "carol"}).status_code == 403
    assert client.patch(f"/api/collections/{cid}", headers=h,
                        json={"nom": "détourné"}).status_code == 403
    assert client.delete(f"/api/collections/{cid}", headers=h).status_code == 403
    # …et il la voit bel et bien : le 403 n'est pas un cloisonnement déguisé.
    assert cid in {c["id"] for c in client.get("/api/collections", headers=h).json()}


def test_collection_invisible_reste_un_404(client, collection_a_alice):
    """Le 403 ci-dessus ne vaut QUE pour ce qu'on voit déjà. Pour un tiers, la collection
    d'alice n'existe pas — sinon le nombre d'études du dépôt se déduirait des codes de
    retour."""
    cid = collection_a_alice["id"]
    h = {"Remote-User": "mallory"}
    assert client.get(f"/api/collections/{cid}/acces", headers=h).status_code == 404
    assert client.patch(f"/api/collections/{cid}", json={"nom": "x"},
                        headers=h).status_code == 404


# --------------------------------------------------------------------------- #
# Accorder et retirer
# --------------------------------------------------------------------------- #
def test_accorder_puis_retirer_un_acces(client, collection_a_alice):
    """Le cycle complet, par la route et non en SQL. `PUT` est idempotent : re-poser le
    même principal met à jour son niveau, ce qui fait de « promouvoir » et « rétrograder »
    le même geste."""
    cid = collection_a_alice["id"]
    h = {"Remote-User": "alice"}
    acces = client.put(f"/api/collections/{cid}/acces", headers=h,
                       json={"principal": "bob", "niveau": "lecture"}).json()
    assert ("bob", "lecture") in {(a["principal"], a["niveau"]) for a in acces}
    # bob lit, mais n'écrit pas encore.
    hb = {"Remote-User": "bob"}
    assert client.post("/api/albums", json={"titre": "refusé", "collection_id": cid},
                       headers=hb).status_code == 404
    acces = client.put(f"/api/collections/{cid}/acces", headers=h,
                       json={"principal": "bob", "niveau": "ecriture"}).json()
    assert ("bob", "ecriture") in {(a["principal"], a["niveau"]) for a in acces}
    assert client.post("/api/albums", json={"titre": "accepté", "collection_id": cid},
                       headers=hb).status_code == 201
    assert client.delete(f"/api/collections/{cid}/acces/utilisateur/bob",
                         headers=h).status_code == 204
    assert client.get("/api/albums", headers=hb).json() == []


def test_accorder_a_un_groupe(client, collection_a_alice):
    """`principal` peut être un nom de GROUPE lu dans `Remote-Groups`. Ce qui est stocké
    est une RÉFÉRENCE au groupe, jamais une appartenance : celle-ci reste chez Authelia et
    se relit à chaque requête (invariant AUTH-1)."""
    cid = collection_a_alice["id"]
    client.put(f"/api/collections/{cid}/acces", headers={"Remote-User": "alice"},
               json={"genre": "groupe", "principal": "bd-lettrage", "niveau": "ecriture"})
    membre = {"Remote-User": "dora", "Remote-Groups": "bd-lettrage"}
    assert cid in {c["id"] for c in client.get("/api/collections", headers=membre).json()}
    # …et le retrait du groupe chez Authelia suffit : rien à défaire en base.
    assert client.get("/api/collections",
                      headers={"Remote-User": "dora"}).json() == []


def test_retirer_un_acces_ne_detruit_aucune_donnee(client, collection_a_alice):
    """Retirer un droit d'entrée n'efface pas ce qui a été fait : le corpus perdrait sa
    provenance à chaque départ. L'album de bob reste, et le journal A3 continue de le lui
    attribuer."""
    cid = collection_a_alice["id"]
    h = {"Remote-User": "alice"}
    client.put(f"/api/collections/{cid}/acces", headers=h,
               json={"principal": "bob", "niveau": "ecriture"})
    alb = client.post("/api/albums", json={"titre": "Travail de bob", "collection_id": cid},
                      headers={"Remote-User": "bob"}).json()
    client.delete(f"/api/collections/{cid}/acces/utilisateur/bob", headers=h)
    restants = client.get("/api/albums", headers=h).json()
    assert alb["id"] in {a["id"] for a in restants}


def test_le_dernier_proprietaire_ne_peut_pas_se_retirer(client, collection_a_alice):
    """Une collection sans propriétaire n'est plus administrable que par un
    administrateur — et ce chantier existe pour ne plus en dépendre. Le refus est un 409
    qui NOMME la contrainte, pas un 403 : ce n'est pas un droit qui manque, c'est un état
    interdit."""
    cid = collection_a_alice["id"]
    h = {"Remote-User": "alice"}
    r = client.delete(f"/api/collections/{cid}/acces/utilisateur/alice", headers=h)
    assert r.status_code == 409 and "dernier propriétaire" in r.json()["detail"]
    r = client.put(f"/api/collections/{cid}/acces", headers=h,
                   json={"principal": "alice", "niveau": "lecture"})
    assert r.status_code == 409                  # se rétrograder revient au même
    # Avec un second propriétaire, le départ redevient possible.
    client.put(f"/api/collections/{cid}/acces", headers=h,
               json={"principal": "bob", "niveau": "proprietaire"})
    assert client.delete(f"/api/collections/{cid}/acces/utilisateur/alice",
                         headers=h).status_code == 204


def test_admin_passe_outre_la_propriete(client, collection_a_alice):
    """Le recours quand quelqu'un quitte le projet en laissant une collection derrière lui.
    Le refuser fabriquerait des collections définitivement bloquées, dont la seule sortie
    serait un UPDATE en SQL — exactement ce que ce chantier supprime."""
    cid = collection_a_alice["id"]
    assert client.get(f"/api/collections/{cid}/acces", headers=ADMIN).status_code == 200
    assert client.put(f"/api/collections/{cid}/acces", headers=ADMIN,
                      json={"principal": "carol",
                            "niveau": "proprietaire"}).status_code == 200


def test_admin_ne_se_declare_pas_proprietaire_en_creant(client, derriere_proxy):
    """Un administrateur possède déjà tout : lui inventer un lien personnel avec chaque
    collection qu'il crée fausserait la notion. S'il veut la posséder, il se l'accorde."""
    c = client.post("/api/collections", json={"nom": "Bac à sable"}, headers=ADMIN).json()
    assert c["acces"] == []
    vue = next(x for x in client.get("/api/collections", headers=ADMIN).json()
               if x["id"] == c["id"])
    assert vue["mon_niveau"] is None and vue["administrable"]


# --------------------------------------------------------------------------- #
# Appartenance des albums (N-N)
# --------------------------------------------------------------------------- #
def test_un_album_vit_dans_plusieurs_collections(client, collection_a_alice):
    """Le schéma est N-N depuis la v14, et c'est porteur de sens : un même album peut
    nourrir deux études, sans duplication — la dupliquer casserait l'analyse inter-corpus,
    qui est la raison d'être du cloisonnement LOGIQUE plutôt que physique."""
    h = {"Remote-User": "alice"}
    c1 = collection_a_alice["id"]
    c2 = client.post("/api/collections", json={"nom": "Représentations 1930-40"},
                     headers=h).json()["id"]
    alb = client.post("/api/albums", json={"titre": "Le Lotus bleu", "collection_id": c1},
                      headers=h).json()
    r = client.put(f"/api/albums/{alb['id']}/collections/{c2}", headers=h)
    assert r.status_code == 201
    assert {c["id"] for c in r.json()} == {c1, c2}


def test_ranger_ailleurs_demande_d_ecrire_des_DEUX_cotes(client, db_path,
                                                         collection_a_alice):
    """Sans droit sur la collection d'ARRIVÉE, on déposerait son travail dans l'étude de
    quelqu'un d'autre. Sans droit sur l'album, on s'approprierait le travail d'un autre en
    le rangeant chez soi."""
    h = {"Remote-User": "alice"}
    c1 = collection_a_alice["id"]
    alb = client.post("/api/albums", json={"titre": "Le Lotus bleu", "collection_id": c1},
                      headers=h).json()
    chez_bob = client.post("/api/collections", json={"nom": "Étude de bob"},
                           headers={"Remote-User": "bob"}).json()["id"]
    # alice ne voit pas la collection de bob : ranger son album dedans est un 404.
    assert client.put(f"/api/albums/{alb['id']}/collections/{chez_bob}",
                      headers=h).status_code == 404
    # …et bob ne peut pas s'approprier l'album d'alice en le rangeant chez lui.
    assert client.put(f"/api/albums/{alb['id']}/collections/{chez_bob}",
                      headers={"Remote-User": "bob"}).status_code == 404


def test_sortir_de_la_derniere_collection_est_refuse(client, collection_a_alice):
    """L'invariant d'AUTH-2 : un album a TOUJOURS une règle d'accès. Le refus nomme la
    contrainte plutôt que de replier silencieusement sur la collection par défaut —
    déplacer, c'est ranger ailleurs PUIS sortir, et l'ordre inverse doit se voir refuser
    au lieu de déverser le travail dans un seau commun."""
    h = {"Remote-User": "alice"}
    c1 = collection_a_alice["id"]
    alb = client.post("/api/albums", json={"titre": "Seul", "collection_id": c1},
                      headers=h).json()
    r = client.delete(f"/api/albums/{alb['id']}/collections/{c1}", headers=h)
    assert r.status_code == 409 and "dernière collection" in r.json()["detail"]
    c2 = client.post("/api/collections", json={"nom": "Ailleurs"}, headers=h).json()["id"]
    client.put(f"/api/albums/{alb['id']}/collections/{c2}", headers=h)
    assert client.delete(f"/api/albums/{alb['id']}/collections/{c1}",
                         headers=h).status_code == 204


def test_supprimer_une_collection_ne_supprime_pas_ses_albums(client, collection_a_alice):
    """L'appartenance est N-N : le lien se défait, l'œuvre reste. Mais supprimer une
    collection ne doit pas fabriquer par ricochet l'orphelin qu'AUTH-2 a retiré du
    modèle — d'où le refus tant qu'un album n'a qu'elle."""
    h = {"Remote-User": "alice"}
    c1 = collection_a_alice["id"]
    alb = client.post("/api/albums", json={"titre": "Le Lotus bleu", "collection_id": c1},
                      headers=h).json()
    r = client.delete(f"/api/collections/{c1}", headers=h)
    assert r.status_code == 409 and "sans aucune règle d'accès" in r.json()["detail"]
    c2 = client.post("/api/collections", json={"nom": "Refuge"}, headers=h).json()["id"]
    client.put(f"/api/albums/{alb['id']}/collections/{c2}", headers=h)
    assert client.delete(f"/api/collections/{c1}", headers=h).status_code == 204
    assert alb["id"] in {a["id"] for a in client.get("/api/albums", headers=h).json()}


def test_les_collections_d_un_album_partage_sont_partielles(client, db_path,
                                                            collection_a_alice):
    """Un album peut légitimement appartenir à une étude à laquelle on ne participe pas.
    La liste est alors PARTIELLE — même compromis que les attributs d'un objet partagé :
    mieux vaut ne pas montrer que révéler l'existence d'une étude voisine."""
    h = {"Remote-User": "alice"}
    c1 = collection_a_alice["id"]
    alb = client.post("/api/albums", json={"titre": "Partagé", "collection_id": c1},
                      headers=h).json()
    autre = client.post("/api/collections", json={"nom": "Étude voisine"},
                        headers=ADMIN).json()["id"]
    client.put(f"/api/albums/{alb['id']}/collections/{autre}", headers=ADMIN)
    vues = client.get(f"/api/albums/{alb['id']}/collections", headers=h).json()
    assert {c["id"] for c in vues} == {c1}                 # l'autre étude n'apparaît pas
    assert {c["id"] for c in client.get(f"/api/albums/{alb['id']}/collections",
                                        headers=ADMIN).json()} == {c1, autre}


# --------------------------------------------------------------------------- #
# Mono-poste
# --------------------------------------------------------------------------- #
def test_mono_poste_voit_et_administre_tout(client):
    """Sans proxy, aucune identité à opposer à personne : la portée est totale et le
    comportement reste STRICTEMENT celui d'avant AUTH-2. La collection naît donc sans
    propriétaire — il n'y a personne à inscrire, et la question est sans objet."""
    c = client.post("/api/collections", json={"nom": "Mon corpus"}).json()
    assert c["acces"] == []
    vue = next(x for x in client.get("/api/collections").json() if x["id"] == c["id"])
    assert vue["mon_niveau"] is None and vue["administrable"]
    assert client.get(f"/api/collections/{c['id']}/acces").json() == []


# --------------------------------------------------------------------------- #
# Ce que la relecture a trouvé — trois écarts, sur une suite verte
# --------------------------------------------------------------------------- #
def test_creer_sans_identite_est_refuse(client, derriere_proxy):
    """« Aucun droit préalable » ne veut pas dire « aucune identité », et la première
    version confondait les deux.

    Derrière le proxy, une requête sans en-tête d'identité n'a jamais traversé Authelia :
    AUTH-2 lui donne une portée VIDE, fermeture par défaut. `POST /api/collections`
    n'exigeant aucun droit, elle échappait à cette règle et ÉCRIVAIT — la seule écriture
    ouverte du dépôt. Le refus est un 403 qui dit la panne probable (forward_auth muet),
    pas un 404 : ce n'est pas un objet qu'on cache, c'est une configuration à réparer.
    """
    r = client.post("/api/collections", json={"nom": "créée par personne"})
    assert r.status_code == 403 and "identité" in r.json()["detail"]
    # …et l'écriture n'a pas eu lieu, pour l'administrateur qui, lui, voit tout.
    assert client.get("/api/collections", headers=ADMIN).json() == []


def test_creer_sans_droit_mais_avec_identite_reste_permis(client, derriere_proxy):
    """La contrepartie, et c'est le geste fondateur : quelqu'un qui n'a AUCUNE collection
    peut en ouvrir une. Le refuser rendrait l'application inutilisable au premier jour de
    chacun — c'est bien l'identité qui est exigée, pas un droit."""
    r = client.post("/api/collections", json={"nom": "Premier jour"},
                    headers={"Remote-User": "nouvelle"})
    assert r.status_code == 201
    assert r.json()["acces"][0]["principal"] == "nouvelle"


def test_statut_de_diffusion_est_un_vocabulaire_controle(client, collection_a_alice):
    """`statut_diffusion` était contrôlé d'un seul côté : `gerer_collections.py` validait,
    la route non. Un champ à deux portes dont une seule contrôle n'est pas contrôlé — la
    liste vit désormais dans `config.py` et les deux chemins la partagent."""
    cid = collection_a_alice["id"]
    h = {"Remote-User": "alice"}
    r = client.patch(f"/api/collections/{cid}", json={"statut_diffusion": "n'importe quoi"},
                     headers=h)
    assert r.status_code == 422 and "Statut de diffusion inconnu" in r.json()["detail"]
    assert client.patch(f"/api/collections/{cid}", json={"statut_diffusion": "embargo"},
                        headers=h).status_code == 200


def test_les_changements_d_acces_sont_traces(client, db_path, collection_a_alice):
    """`peut_administrer` se justifie par la TRAÇABILITÉ : un accès accordé par erreur doit
    pouvoir se retrouver. Sans trace, l'argument ne tenait pas — écart relevé en relisant
    ma propre justification, pas par un test rouge.

    Ces événements ne sont pas annulables : `undo._TABLES` est une liste blanche, et
    `collection_acces` n'y figure pas. Défaire un partage par Ctrl+Z serait une surprise.
    """
    import sqlite3
    import undo
    cid = collection_a_alice["id"]
    h = {"Remote-User": "alice"}
    client.put(f"/api/collections/{cid}/acces", headers=h,
               json={"principal": "bob", "niveau": "ecriture"})
    client.delete(f"/api/collections/{cid}/acces/utilisateur/bob", headers=h)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        actes = conn.execute(
            "SELECT type, agent, apres, avant FROM evenement "
            "WHERE cible_table = 'collection_acces' AND cible_id = ? ORDER BY id",
            (cid,)).fetchall()
    finally:
        conn.close()
    assert [a["type"] for a in actes] == ["lien", "delien"]
    assert all(a["agent"] == "alice" for a in actes)          # QUI a ouvert à qui
    assert "bob" in actes[0]["apres"] and "bob" in actes[1]["avant"]
    assert "collection_acces" not in undo._TABLES             # jamais annulable


def test_le_nom_du_repli_est_reserve(client, collection_a_alice):
    """Un écart OUVERT par ce chantier même, et mesuré avant d'être fermé.

    `database.collection_par_defaut` désigne le repli PAR SON NOM. Tant que renommer une
    collection exigeait un accès shell, le seul mode d'échec était « quelqu'un renomme le
    repli » — bénin, un nouveau seau vide se recrée. AUTH-3 a donné le renommage à tout
    propriétaire, et rendu possible l'inverse : s'attribuer ce nom capture les albums créés
    sans collection explicite. Mesuré sur la version d'avant : un album d'ADMINISTRATEUR
    atterrissait dans la collection du renommeur, et lui devenait visible.

    C'est exactement le mode d'échec que le choix du nom disait éviter (cf. le commentaire
    de `NOM_COLLECTION_DEFAUT`). La garde vaut aussi à la création, et dans l'outil headless.
    """
    import database
    h = {"Remote-User": "alice"}
    r = client.post("/api/collections", json={"nom": database.NOM_COLLECTION_DEFAUT},
                    headers=h)
    assert r.status_code == 422 and "réservé" in r.json()["detail"]
    r = client.patch(f"/api/collections/{collection_a_alice['id']}",
                     json={"nom": database.NOM_COLLECTION_DEFAUT}, headers=h)
    assert r.status_code == 422
    # La casse ne contourne pas : c'est un nom réservé, pas une chaîne à comparer.
    assert client.post("/api/collections",
                       json={"nom": database.NOM_COLLECTION_DEFAUT.upper()},
                       headers=h).status_code == 422


def test_le_repli_garde_son_propre_nom(client, db_path, derriere_proxy):
    """La garde ne doit pas emprisonner le repli lui-même : il reste éditable (description,
    licence) sans qu'on lui interdise de conserver son nom."""
    import database
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        cid = conn.execute("INSERT INTO collection (nom) VALUES (?)",
                           (database.NOM_COLLECTION_DEFAUT,)).lastrowid
        conn.commit()
    finally:
        conn.close()
    r = client.patch(f"/api/collections/{cid}",
                     json={"nom": database.NOM_COLLECTION_DEFAUT,
                           "description": "Le seau de repli."}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["description"] == "Le seau de repli."


def test_sortir_d_une_collection_etrangere_dit_la_verite(client, collection_a_alice):
    """Le garde-fou « dernière collection » se déclenchait AVANT de vérifier l'appartenance,
    et répondait donc « c'est la dernière collection de cet album » pour une collection dont
    l'album ne faisait pas partie. Une phrase fausse sur une opération sans objet : un
    message d'erreur qui ment coûte plus cher que pas de message du tout."""
    h = {"Remote-User": "alice"}
    c1 = collection_a_alice["id"]
    autre = client.post("/api/collections", json={"nom": "Sans rapport"},
                        headers=h).json()["id"]
    alb = client.post("/api/albums", json={"titre": "Ailleurs", "collection_id": c1},
                      headers=h).json()
    r = client.delete(f"/api/albums/{alb['id']}/collections/{autre}", headers=h)
    assert r.status_code == 404 and "n'appartient pas" in r.json()["detail"]
