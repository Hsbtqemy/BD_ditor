"""AUTH-2 — le point de passage de l'autorisation, et le test qui empêche de l'oublier.

Le risque de ce chantier n'est pas la difficulté, c'est l'exhaustivité. Il y a plus de
cent routes ; une règle d'accès qui en couvre toutes sauf une ne cloisonne rien, et le
trou ne se voit pas puisque tout marche. Le premier test de ce fichier est donc plus important que tous les autres :
il énumère les routes de l'application et exige que CHACUNE ait été tranchée — soit elle
consulte la portée, soit elle figure sur une liste écrite avec sa raison.

Ce que ce test NE fait PAS, et qu'il ne faut pas lui prêter : il vérifie qu'une route
*consulte* la portée, pas qu'elle en tire la bonne conclusion. Une route peut déclarer la
dépendance et filtrer de travers. C'est le rôle des tests de comportement plus bas, dont
la couverture est une LISTE, pas une garantie — et elle est bien plus courte que le
nombre de routes. Dit autrement : le test statique ferme la porte de l'oubli, pas celle de l'erreur.
"""
import json

import pytest

import autorisation
import inventaire_routes
import main


# --------------------------------------------------------------------------- #
# Ce qui ne consulte pas la portée, et pourquoi
# --------------------------------------------------------------------------- #
# Une route est ici parce qu'on a décidé qu'elle y soit, avec la raison écrite à côté.
# Ajouter une ligne ici est un ACTE : c'est déclarer qu'une route peut toucher au serveur
# sans demander qui appelle.
#
# DEUX EN SONT SORTIES le 2026-08-28 (DROIT-1) : les deux routes de sauvegarde. Leur raison
# écrite portait sa propre condition de réouverture — « dès qu'un tiering de droits est
# effectif, cette décision se rejoue » — et cette liste est ce qui l'a rendue impossible à
# oublier : la changer supposait de la relire.
#
# QUATRE AUTRES le 2026-08-28 (SHARE-1) : les routes de session ShareDocs. Elles ne
# touchent toujours pas au corpus — leur raison d'être ici restait vraie — mais elles
# consultent désormais QUI appelle, pour ranger les identifiants sous le bon principal et
# pour réserver le compte de l'instance aux administrateurs. Une de leurs lignes disait
# d'ailleurs « session par personne : cf. SHARE-1 » : la liste portait sa propre échéance.
HORS_PERIMETRE = {
    ("GET", "/"): "coquille HTML, aucune donnée — le contenu vient des routes /api",
    ("GET", "/recherche"): "idem",
    ("GET", "/corpus"): "idem",
    ("GET", "/exploration"): "idem",
    ("GET", "/administration"): (
        "idem — et la coquille est ici une DÉCISION, pas une commodité (UX-10). Chaque "
        "bloc de cette page pose sa propre question : la liste des collections est "
        "filtrée par la portée, `GET /api/comptes` refuse les non-administrateurs, "
        "`GET /api/sante` est ouvert à tous. Garder la PAGE reproduirait l'erreur "
        "d'AUTH-4, où le référent d'une collection s'est retrouvé réservé au "
        "propriétaire parce qu'il vivait dans le panneau du partage"),
    ("GET", "/api/sante"): (
        "état des moteurs ML, aucune donnée de corpus. Doit rester joignable sans "
        "identité : c'est la sonde d'un conteneur, appelée avant qu'Authelia ne soit "
        "forcément debout"),
    ("GET", "/api/figure/champs"): (
        "décrit le FORMAT d'une légende de figure (DROIT-1), pas un corpus : elle "
        "renverrait la même chose sur une instance vide"),
}

# --------------------------------------------------------------------------- #
# Ce qui reste à câbler — la dette, nommée
# --------------------------------------------------------------------------- #
# Cette liste doit atteindre ZÉRO. Elle existe pour que le chantier soit livrable par
# tranches sans que la suite passe au vert en prétendant couvrir ce qu'elle ne couvre
# pas : chaque ligne est une route qui touche aux données SANS demander qui appelle.
#
# Elle a aussi un effet de cliquet : une route absente des DEUX listes fait échouer la
# suite. On ne peut donc pas ajouter une route non cloisonnée sans s'en apercevoir.
A_CABLER = {
}


# Montages autorisés à servir des fichiers sans contrôle d'accès. Un montage n'est PAS
# une route : il échappe entièrement au cliquet ci-dessous, d'où sa propre liste.
#
# C'est là qu'était la plus large fuite du dépôt, trouvée le 2026-08-27 en relisant et non
# par un test : `/derivatives` était un `StaticFiles` servant l'image web de TOUTE planche
# à un chemin parfaitement devinable — tout le corpus restait lisible en image quelle que
# soit la rigueur des routes JSON. Il est devenu une route cloisonnée.
MONTAGES_AUTORISES = {
    "/static": "CSS/JS de l'application — aucune donnée de corpus",
}


def _routes() -> list[tuple[str, str, bool]]:
    """(méthode, chemin, consulte-t-elle la portée ?) pour chaque route de l'app.

    L'énumération et la marche des dépendances vivent dans `inventaire_routes` (ARCH-2).
    Elles étaient ici, et elles y filtraient sur `isinstance(r, APIRoute)` : à partir de
    FastAPI 0.137, un routeur inclus n'aplatit plus ses routes dans `app.routes`, l'objet
    paresseux qui le remplace n'est pas une `APIRoute`, et ce filtre a écarté 69 des
    122 routes SANS RIEN DIRE. Le cliquet ci-dessous est resté vert en n'ayant examiné que
    44 % du contrat qu'il prétend garder.
    """
    out = []
    for r in inventaire_routes.routes_api():
        scopee = main.portee_courante in inventaire_routes.dependances(r)
        for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
            out.append((m, r.path, scopee))
    return out


# --------------------------------------------------------------------------- #
# Le cliquet
# --------------------------------------------------------------------------- #
def test_toute_route_est_tranchee():
    """Aucune route ne peut exister sans qu'on ait décidé de son cloisonnement.

    C'est LA protection du chantier. Sans elle, ajouter une route qui lit la base sans
    portée passerait inaperçue : elle marcherait parfaitement, et fuirait.
    """
    inconnues = [
        (m, c) for m, c, scopee in _routes()
        if not scopee and (m, c) not in HORS_PERIMETRE and (m, c) not in A_CABLER
    ]
    assert not inconnues, (
        "Ces routes ne consultent pas la portée d'autorisation et ne figurent sur aucune "
        "liste écrite. Décidez : soit elles prennent "
        "`portee: autorisation.Portee = Depends(portee_courante)` et filtrent, soit elles "
        "entrent dans HORS_PERIMETRE avec leur raison.\n  "
        + "\n  ".join(f"{m} {c}" for m, c in inconnues))


def test_l_inventaire_des_routes_n_a_pas_retreci():
    """Le cliquet ci-dessus doit ÉCHOUER quand il cesse de voir, pas passer plus vite.

    Il ne prouve RIEN sur un inventaire vide : « aucune route non tranchée » est vrai de
    zéro route. C'est exactement ce qui est arrivé le 2026-09-05 — FastAPI 0.137 a cessé
    d'aplatir les routeurs inclus dans `app.routes`, le filtre `isinstance(r, APIRoute)` a
    écarté 69 routes en silence, et ce fichier est resté vert en n'ayant examiné que 53
    routes sur 122. Une garde qui tombe est un incident ; une garde qui approuve en n'ayant
    rien vu est un mensonge, et personne ne l'entend.

    Le plancher se DÉRIVE du source (`inventaire_routes.plancher_source`, compté par AST
    sur `main.py` et `routes/*.py`) et non d'un chiffre écrit ici. Un chiffre recopié
    vieillit, et il vieillit dans le sens permissif : l'application grossit, le nombre
    reste, et la marge silencieuse remplace la garde.
    """
    inventaire_routes.exiger_plancher(len(_routes()), "le cliquet d'autorisation (AUTH-2)")


def test_aucun_montage_ne_sert_le_corpus():
    """Un montage de fichiers statiques ne passe par AUCUNE dépendance : le cliquet des
    routes ne peut pas le voir. Il lui faut donc sa propre porte."""
    inconnus = [m.path for m in inventaire_routes.montages()
                if m.path not in MONTAGES_AUTORISES]
    assert not inconnus, (
        "Ces montages servent des fichiers sans contrôle d'accès. Un montage échappe à "
        "toute dépendance : s'il touche au corpus, il doit devenir une route.\n  "
        + "\n  ".join(inconnus))


def test_les_listes_ne_mentent_pas():
    """Une route listée qui a été câblée entre-temps doit sortir de la liste — sinon la
    dette affichée est plus grosse que la vraie, et on cesse de la croire."""
    scopees = {(m, c) for m, c, s in _routes() if s}
    en_trop = sorted((scopees & set(A_CABLER)) | (scopees & set(HORS_PERIMETRE)))
    assert not en_trop, (
        "Ces routes consultent la portée mais figurent encore sur une liste : "
        f"retirez-les.\n  " + "\n  ".join(f"{m} {c}" for m, c in en_trop))


def test_dette_de_cablage_visible(capsys):
    """N'échoue pas : AFFICHE la dette. Un chantier livré par tranches doit dire où il
    en est, sinon une suite verte se lit comme « tout est cloisonné »."""
    total = len(_routes())
    scopees = sum(1 for *_, s in _routes() if s)
    with capsys.disabled():
        print(f"\n  AUTH-2 — {scopees}/{total} routes cloisonnées, "
              f"{len(A_CABLER)} à câbler, {len(HORS_PERIMETRE)} hors périmètre écrit")


# --------------------------------------------------------------------------- #
# La portée elle-même
# --------------------------------------------------------------------------- #
def test_sans_proxy_la_portee_est_totale():
    """Le mono-poste ne change PAS de comportement. Une seule personne devant sa machine
    n'a personne à qui s'opposer ; cloisonner sans savoir qui est là rendrait l'outil
    inutilisable en local."""
    class Req:
        headers = {}
    p = autorisation.resoudre(None, Req())     # conn jamais touchée : court-circuit
    assert p.tout and p.admin
    assert p.clause_album("a.id") == ("1", [])


def test_derriere_proxy_sans_identite_la_portee_est_vide(derriere_proxy):
    """Fermeture par défaut : une requête qui n'est pas passée par Authelia ne voit rien.

    Conséquence à connaître, et voulue : si le proxy est mal configuré, l'application
    paraît VIDE pour tout le monde. Panne bruyante plutôt que fuite silencieuse.
    """
    class Req:
        headers = {}
    p = autorisation.resoudre(None, Req())
    assert not p.tout and not p.admin and not p.lecture
    assert p.clause_album("a.id") == ("0", [])


def test_groupe_admin_voit_tout(derriere_proxy):
    class Req:
        headers = {"Remote-User": "alice", "Remote-Groups": "bd-admins, autre"}
    p = autorisation.resoudre(None, Req())
    assert p.tout and p.admin and p.utilisateur == "alice"


def test_ecrire_implique_lire():
    p = autorisation.Portee(lecture=frozenset({1}), ecriture=frozenset({2}))
    assert p.peut_lire(1) and not p.peut_ecrire(1)
    assert p.peut_lire(2) and p.peut_ecrire(2)


def test_clause_album_lie_ses_parametres():
    """Les ids de collection passent en paramètres liés, jamais concaténés : ils viennent
    de la base, mais un contrôle d'accès n'est pas l'endroit où l'on se fie à ça."""
    p = autorisation.Portee(lecture=frozenset({3, 1}))
    sql, params = p.clause_album("a.id")
    assert params == [1, 3]                     # triés : SQL stable, cache de plan stable
    assert "?" in sql and "1, 3" not in sql


def test_portee_vide_ne_selectionne_rien():
    sql, params = autorisation.Portee().clause_album("a.id")
    assert (sql, params) == ("0", [])


# --------------------------------------------------------------------------- #
# L'invariant : aucun album hors collection
# --------------------------------------------------------------------------- #
def test_aucun_album_orphelin_apres_creation(client, db_path):
    """La collection étant l'unité de cloisonnement, un album hors collection ne
    correspondrait à AUCUNE règle d'accès. On ne tranche pas ce cas : on le supprime."""
    import database
    for titre in ("Un", "Deux"):
        assert client.post("/api/albums", json={"titre": titre}).status_code == 201
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        assert database.albums_orphelins(conn) == []
    finally:
        conn.close()


def test_collection_par_defaut_est_idempotente(client, db_path):
    """Deux albums créés d'affilée ne créent pas deux collections de repli."""
    import sqlite3
    import database
    client.post("/api/albums", json={"titre": "A"})
    client.post("/api/albums", json={"titre": "B"})
    conn = sqlite3.connect(db_path)
    try:
        n = conn.execute("SELECT COUNT(*) FROM collection WHERE nom = ?",
                         (database.NOM_COLLECTION_DEFAUT,)).fetchone()[0]
        assert n == 1
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Comportement de bout en bout
# --------------------------------------------------------------------------- #
def _ouvrir(db_path, collection_id, principal, niveau="lecture", genre="utilisateur"):
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT OR REPLACE INTO collection_acces "
                     "(collection_id, genre, principal, niveau) VALUES (?, ?, ?, ?)",
                     (collection_id, genre, principal, niveau))
        conn.commit()
    finally:
        conn.close()


def _collection_de(db_path, album_id) -> int:
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT collection_id FROM collection_album WHERE album_id = ?",
                            (album_id,)).fetchone()[0]
    finally:
        conn.close()


@pytest.fixture
def deux_albums(client, db_path, png_bytes):
    """Deux albums, chacun dans SA collection, chacun avec une planche et une région.

    Le décor est monté avec `ADMIN` plutôt qu'en comptant sur l'ordre des fixtures
    (`derriere_proxy` vient après) : un ordre implicite se casse sans bruit, des en-têtes
    explicites non — et hors proxy ils n'ont aucun effet.
    """
    import sqlite3
    from conftest import ADMIN
    a1 = client.post("/api/albums", json={"titre": "Autorisé"}, headers=ADMIN).json()
    a2 = client.post("/api/albums", json={"titre": "Interdit"}, headers=ADMIN).json()
    pl1 = client.post(f"/api/albums/{a1['id']}/import", headers=ADMIN,
                      files={"file": ("p.png", png_bytes, "image/png")}).json()
    pl2 = client.post(f"/api/albums/{a2['id']}/import", headers=ADMIN,
                      files={"file": ("p.png", png_bytes, "image/png")}).json()
    r1 = client.post(f"/api/planches/{pl1['id']}/regions", headers=ADMIN,
                     json={"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9}).json()
    r2 = client.post(f"/api/planches/{pl2['id']}/regions", headers=ADMIN,
                     json={"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9}).json()
    client.put(f"/api/regions/{r1['id']}", json={"ocr_texte": "MOTSECRET ici"}, headers=ADMIN)
    client.put(f"/api/regions/{r2['id']}", json={"ocr_texte": "MOTSECRET ailleurs"},
               headers=ADMIN)
    conn = sqlite3.connect(db_path)
    try:
        c2 = conn.execute("INSERT INTO collection (nom) VALUES ('Étude B')").lastrowid
        conn.execute("DELETE FROM collection_album WHERE album_id = ?", (a2["id"],))
        conn.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                     (c2, a2["id"]))
        conn.commit()
    finally:
        conn.close()
    return {"c1": _collection_de(db_path, a1["id"]), "c2": c2,
            "a1": a1, "a2": a2, "pl1": pl1, "pl2": pl2, "r1": r1, "r2": r2}


def test_planche_hors_portee_est_introuvable(client, db_path, deux_albums, derriere_proxy):
    """404, pas 403 : « cet objet existe mais pas pour vous » révèle la composition du
    corpus. L'absence est la seule réponse qui ne fuit rien."""
    _ouvrir(db_path, deux_albums["c1"], "bob")      # bob n'a QUE la collection 1
    r = client.get(f"/api/planches/{deux_albums['pl2']['id']}/regions",
                   headers={"Remote-User": "bob"})
    assert r.status_code == 404


def test_planche_dans_la_portee_reste_accessible(client, db_path, deux_albums,
                                                 derriere_proxy):
    _ouvrir(db_path, deux_albums["c1"], "bob")
    r = client.get(f"/api/planches/{deux_albums['pl1']['id']}/regions",
                   headers={"Remote-User": "bob"})
    assert r.status_code == 200


def test_la_liste_d_albums_est_filtree(client, db_path, deux_albums, derriere_proxy):
    """La fuite la plus banale n'est pas l'accès direct, c'est la LISTE : elle donne les
    titres, donc l'existence des études voisines."""
    _ouvrir(db_path, deux_albums["c1"], "bob")
    titres = [a["titre"] for a in
              client.get("/api/albums", headers={"Remote-User": "bob"}).json()]
    assert titres == ["Autorisé"]


def test_le_droit_par_groupe_ouvre_comme_le_droit_nominal(client, db_path, deux_albums,
                                                          derriere_proxy):
    """Le droit se donne à un login OU à un nom de groupe. L'appartenance au groupe, elle,
    n'est jamais stockée : elle est relue dans `Remote-Groups` à chaque requête."""
    _ouvrir(db_path, deux_albums["c1"], "bd-lettrage", genre="groupe")
    url = f"/api/planches/{deux_albums['pl1']['id']}/regions"
    r = client.get(url, headers={"Remote-User": "carol", "Remote-Groups": "bd-lettrage"})
    assert r.status_code == 200
    # la même personne SANS le groupe ne voit rien : rien n'a été mémorisé en base
    assert client.get(url, headers={"Remote-User": "carol"}).status_code == 404


def test_lecture_seule_ne_permet_pas_d_ecrire(client, db_path, deux_albums, derriere_proxy):
    _ouvrir(db_path, deux_albums["c1"], "bob", niveau="lecture")
    h = {"Remote-User": "bob"}
    pid = deux_albums["pl1"]["id"]
    assert client.get(f"/api/planches/{pid}/regions", headers=h).status_code == 200
    assert client.patch(f"/api/planches/{pid}/statut",
                        json={"statut": "annotee"}, headers=h).status_code == 404


def test_ecriture_permet_d_ecrire(client, db_path, deux_albums, derriere_proxy):
    _ouvrir(db_path, deux_albums["c1"], "bob", niveau="ecriture")
    r = client.patch(f"/api/planches/{deux_albums['pl1']['id']}/statut",
                     json={"statut": "annotee"}, headers={"Remote-User": "bob"})
    assert r.status_code == 200


def test_creer_un_album_sans_droit_d_ecriture_est_refuse(client, deux_albums,
                                                         derriere_proxy):
    """403 et non 404 : ce refus parle des droits de l'appelant, pas de l'existence
    d'une collection. Il ne fuit donc rien, et il est actionnable."""
    r = client.post("/api/albums", json={"titre": "Clandestin"},
                    headers={"Remote-User": "bob"})
    assert r.status_code == 403


def test_creer_dans_une_collection_interdite_donne_404(client, db_path, deux_albums,
                                                       derriere_proxy):
    """Interdite et inexistante se répondent PAREIL, sans quoi l'un des deux cas
    révélerait l'existence de l'autre."""
    _ouvrir(db_path, deux_albums["c1"], "bob", niveau="ecriture")
    h = {"Remote-User": "bob"}
    interdite = client.post("/api/albums",
                            json={"titre": "X", "collection_id": deux_albums["c2"]},
                            headers=h)
    inexistante = client.post("/api/albums",
                              json={"titre": "X", "collection_id": 99999},
                              headers=h)
    assert interdite.status_code == inexistante.status_code == 404
    assert interdite.json()["detail"].split()[0] == inexistante.json()["detail"].split()[0]


def test_la_recherche_plein_texte_est_cloisonnee(client, db_path, deux_albums,
                                                 derriere_proxy):
    """Le piège le plus vicieux du dépôt : la table FTS `recherche` est dénormalisée et
    GLOBALE — elle agrège OCR, note, tags et lemmes sans porter trace d'album ni de
    collection. Une requête non filtrée renverrait tout le corpus, quelle que soit la
    rigueur des routes de lecture par identifiant."""
    _ouvrir(db_path, deux_albums["c1"], "bob")
    trouves = client.get("/api/recherche?q=MOTSECRET",
                         headers={"Remote-User": "bob"}).json()
    assert trouves["count"] == 1
    assert trouves["results"][0]["region_id"] == deux_albums["r1"]["id"]


def test_l_export_csv_de_recherche_suit_la_meme_regle(client, db_path, deux_albums,
                                                      derriere_proxy):
    """Deux routes, une seule logique de requête : l'export ne doit pas être la porte
    dérobée de la recherche."""
    _ouvrir(db_path, deux_albums["c1"], "bob")
    csv = client.get("/api/recherche/export.csv?q=MOTSECRET",
                     headers={"Remote-User": "bob"}).text
    assert "ailleurs" not in csv       # la région interdite n'y est pas
    assert "ici" in csv                # celle qu'on a le droit de voir, si


def test_les_compteurs_du_corpus_sont_cloisonnes(client, db_path, deux_albums,
                                                 derriere_proxy):
    """La composition du corpus fuit par les NOMBRES aussi bien que par les titres."""
    _poser_tag(db_path, "commun")
    _poser_tag(db_path, "prive", deux_albums["c2"])
    _ouvrir(db_path, deux_albums["c1"], "bob")
    c = client.get("/api/corpus", headers={"Remote-User": "bob"}).json()
    assert c["albums"] == 1 and c["planches"] == 1
    # `tags` suit la règle du VOCABULAIRE, pas celle des données : le global compte,
    # le local à une collection fermée non.
    assert c["tags"] == 1


@pytest.mark.parametrize("route", ["/api/export/json", "/api/export/csv", "/api/export/tei"])
def test_les_exports_n_exposent_pas_ce_que_l_ui_cache(client, db_path, deux_albums,
                                                      derriere_proxy, route):
    """Un export est une porte aussi large que l'UI, et plus discrète. Les trois
    sérialisations (JSON-LD, CSV, TEI) suivent la même règle que l'affichage."""
    _ouvrir(db_path, deux_albums["c1"], "bob")
    h = {"Remote-User": "bob"}
    assert client.get(f"{route}?album_id={deux_albums['a2']['id']}",
                      headers=h).status_code == 404
    assert client.get(f"{route}?album_id={deux_albums['a1']['id']}",
                      headers=h).status_code == 200


def _poser_token(db_path, region_id, lemme):
    """Écrit un token directement, sans passer par spaCy : le test doit prouver le
    FILTRAGE, pas dépendre de la présence d'un moteur optionnel."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
                     "VALUES (?, 0, ?, ?, 'NOUN', '')", (region_id, lemme, lemme))
        conn.commit()
    finally:
        conn.close()


def test_les_surfaces_d_analyse_sont_cloisonnees(client, db_path, deux_albums,
                                                 derriere_proxy):
    """Les quatre surfaces d'analyse partagent `_analyse_filtres` : le cloisonnement se
    pose au seul endroit qu'elles ont en commun, pas quatre fois."""
    import sqlite3
    _poser_token(db_path, deux_albums["r1"]["id"], "visible")
    _poser_token(db_path, deux_albums["r2"]["id"], "interdit")
    # le décor n'est PAS vide : sans cette garde, un filtre trop large passerait pour
    # un filtre correct (il n'y aurait simplement rien à voir).
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM tokens WHERE lemme = 'interdit'"
                            ).fetchone()[0] == 1
    finally:
        conn.close()

    _ouvrir(db_path, deux_albums["c1"], "bob")
    h = {"Remote-User": "bob"}
    freq = client.get("/api/analyse/frequences?champ=lemme", headers=h).json()
    lemmes = {r["lemme"] for r in freq["results"]}
    assert "visible" in lemmes and "interdit" not in lemmes

    conc = client.get("/api/analyse/concordance?lemme=interdit", headers=h).json()
    assert conc["count"] == 0


def test_un_lot_ne_montre_pas_les_travaux_des_autres(client, db_path, deux_albums,
                                                     derriere_proxy):
    """La progression d'un lot cite des planches, donc des albums : elle révèle
    l'existence d'études voisines sans jamais en afficher le contenu."""
    import pipeline.jobs as jobs_mod
    jobs_mod._jobs[1] = {"id": 1, "passes": ["ocr"],
                         "planche_ids": [deux_albums["pl2"]["id"]],
                         "total": 1, "done": 0, "current": None,
                         "errors": [], "status": "en_cours", "cancel": False}
    _ouvrir(db_path, deux_albums["c1"], "bob")
    h = {"Remote-User": "bob"}
    assert client.get("/api/jobs", headers=h).json() == []
    assert client.get("/api/jobs/1", headers=h).status_code == 404
    assert client.post("/api/jobs/1/annuler", headers=h).status_code == 404


def test_un_job_inconnu_n_est_visible_de_personne(client, db_path, deux_albums,
                                                  derriere_proxy):
    """CONC-1 — la garde approuvait un job qui n'existe pas.

    `planches_du_job` rendait `[]` pour un identifiant inconnu, et l'ensemble vide est
    inclus dans n'importe quel autre : `set([]) <= autorisees` vaut True quelle que soit
    la portée, y compris une portée qui n'autorise rien.

    **Ce test porte sur la PRIMITIVE et non sur les routes, et c'est tout le point.** Par
    les routes, la réponse est un 404 avant comme après le correctif — chacune teste
    l'existence par ailleurs. Le défaut n'était donc visible nulle part, et ce qui
    protégeait était l'ORDRE des vérifications à chaque appel, jamais la garde elle-même :
    correct par accident, pas par construction. La purge du registre que CONC-1 demande
    fera de « job inconnu » l'état FINAL de tous les jobs, et chargera ce ressort.

    Les trois portées sont éprouvées exprès, dont `tout=True` : une portée totale
    court-circuite les ensembles, et c'est le chemin par lequel un mono-poste ou un
    administrateur aurait obtenu `True` même après un correctif posé au mauvais endroit.
    """
    import sqlite3
    import pipeline.jobs as jobs_mod

    inconnu = 999_999
    assert inconnu not in jobs_mod._jobs
    assert jobs_mod.planches_du_job(inconnu) is None, (
        "un job inconnu doit rester DISTINGUABLE d'un job sans planche : une liste vide "
        "rend les deux identiques, et c'est ce qui rendait la garde permissive")

    conn = sqlite3.connect(db_path)
    try:
        for portee in (autorisation.Portee(),                            # n'autorise rien
                       autorisation.Portee(lecture=frozenset({deux_albums["c1"]})),
                       autorisation.Portee(tout=True)):                  # mono-poste, admin
            assert main._job_visible(conn, portee, inconnu) is False
            assert main._job_visible(conn, portee, inconnu, ecriture=True) is False
    finally:
        conn.close()


def test_liberer_les_modeles_est_reserve_aux_administrateurs(client, deux_albums,
                                                             derriere_proxy):
    """403 et non 404 : le verrou ML est global, le refus parle des droits de l'appelant
    et ne dit rien du corpus."""
    assert client.post("/api/ml/liberer",
                       headers={"Remote-User": "bob"}).status_code == 403
    assert client.post("/api/ml/liberer",
                       headers={"Remote-User": "root",
                                "Remote-Groups": "bd-admins"}).status_code == 200


def test_une_image_hors_portee_est_introuvable(client, db_path, deux_albums,
                                               derriere_proxy):
    """L'image web d'une planche se demande à un chemin devinable. Si elle échappe au
    cloisonnement, tout le corpus reste lisible — en images plutôt qu'en JSON."""
    _ouvrir(db_path, deux_albums["c1"], "bob")
    h = {"Remote-User": "bob"}
    assert client.get("/" + deux_albums["pl1"]["chemin_web"], headers=h).status_code == 200
    assert client.get("/" + deux_albums["pl2"]["chemin_web"], headers=h).status_code == 404


def test_le_chemin_d_image_ne_traverse_pas_les_repertoires(client, deux_albums):
    """La base sert d'allowlist : un chemin qui n'est pas dans `planches.chemin_web` n'est
    jamais servi, `..` compris. C'est ce que garantissait `StaticFiles` et qu'il fallait
    ne pas perdre en le remplaçant."""
    assert client.get("/derivatives/../bd_annotator.sqlite").status_code == 404
    assert client.get("/derivatives/album_1/inexistante.jpg").status_code == 404


# --------------------------------------------------------------------------- #
# Le vocabulaire — une règle différente, et voulue
# --------------------------------------------------------------------------- #
def _poser_tag(db_path, label, collection_id=None):
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO tags (label, collection_id) VALUES (?, ?)",
                     (label, collection_id))
        conn.commit()
    finally:
        conn.close()


def test_un_terme_global_reste_visible_un_terme_local_non(client, db_path, deux_albums,
                                                          derriere_proxy):
    """Le vocabulaire ne suit PAS la règle des données : il porte sa propre portée depuis
    le lexique situé (A4). `collection_id` NULL veut dire global, et c'est un état voulu."""
    _poser_tag(db_path, "commun")                        # global
    _poser_tag(db_path, "prive", deux_albums["c2"])      # local à la collection interdite
    _ouvrir(db_path, deux_albums["c1"], "bob")
    labels = {t["label"] for t in
              client.get("/api/tags", headers={"Remote-User": "bob"}).json()}
    assert "commun" in labels and "prive" not in labels


def test_la_frequence_d_un_tag_ne_compte_que_le_lisible(client, db_path, deux_albums,
                                                        derriere_proxy):
    """Un nuage de tags dont les comptes portent sur tout le corpus dit le volume de
    travail des autres — et fausse la lecture du sous-corpus qu'on regarde."""
    from conftest import ADMIN
    for r in ("r1", "r2"):
        client.put(f"/api/regions/{deux_albums[r]['id']}/annotation",
                   json={"note": "", "tags": ["partout"]}, headers=ADMIN)
    # garde anti-vacuité : sans elle, un tag qui ne serait posé QU'UNE fois donnerait le
    # même 1 et le test passerait sans rien mesurer.
    vus = {t["label"]: t["frequence"] for t in
           client.get("/api/tags", headers=ADMIN).json()}
    assert vus["partout"] == 2

    _ouvrir(db_path, deux_albums["c1"], "bob")
    tags = client.get("/api/tags", headers={"Remote-User": "bob"}).json()
    freq = {t["label"]: t["frequence"] for t in tags}
    assert freq["partout"] == 1                  # posé sur deux régions, une seule lisible


def test_une_ligne_de_concordance_tait_un_tag_local_illisible(client, db_path, deux_albums,
                                                              derriere_proxy):
    """ANA-6 — une ligne de concordance montre les tags de sa région, mais pas TOUS.

    Un tag peut devenir local après avoir été posé, et un album vit dans plusieurs
    collections : une région qu'on lit peut donc porter un tag d'une collection qu'on ne
    lit pas. Son nom est un morceau de grille d'analyse — la raison même de la portée des
    termes (v24). La garde anti-vacuité exige que l'administrateur voie les DEUX d'abord.
    """
    import sqlite3
    from conftest import ADMIN
    _poser_tag(db_path, "prive", deux_albums["c2"])      # local à la collection interdite
    r1 = deux_albums["r1"]["id"]
    client.put(f"/api/regions/{r1}/annotation",
               json={"note": "", "tags": ["prive", "commun"]}, headers=ADMIN)
    conn = sqlite3.connect(db_path)                      # APRÈS l'annotation : elle réindexe
    try:
        conn.execute("INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
                     "VALUES (?, 0, 'DIS', 'dire', 'VERB', '')", (r1,))
        conn.commit()
    finally:
        conn.close()

    def tags_vus(h):
        rep = client.get("/api/analyse/concordance", params={"lemme": "dire"}, headers=h)
        return {t["label"] for ligne in rep.json()["results"] for t in ligne["tags"]}

    assert tags_vus(ADMIN) == {"prive", "commun"}
    _ouvrir(db_path, deux_albums["c1"], "bob")
    assert tags_vus({"Remote-User": "bob"}) == {"commun"}


def test_creer_un_terme_en_lecture_seule_est_refuse(client, db_path, deux_albums,
                                                    derriere_proxy):
    """403 : enrichir un vocabulaire que tout le monde partage suppose de pouvoir écrire
    quelque part. Le refus parle des droits de l'appelant, il ne fuit rien."""
    _ouvrir(db_path, deux_albums["c1"], "bob", niveau="lecture")
    h = {"Remote-User": "bob"}
    assert client.post("/api/tags", json={"label": "x"}, headers=h).status_code == 403
    assert client.post("/api/domaines", json={"nom": "y"}, headers=h).status_code == 403


def test_les_collections_listees_sont_les_siennes(client, db_path, deux_albums,
                                                  derriere_proxy):
    """Les NOMS de collections disent quelles études existent — et le menu de portée du
    lexique proposerait sinon de ranger un terme chez quelqu'un d'autre."""
    _ouvrir(db_path, deux_albums["c1"], "bob")
    ids = {c["id"] for c in
           client.get("/api/collections", headers={"Remote-User": "bob"}).json()}
    assert ids == {deux_albums["c1"]}


# --------------------------------------------------------------------------- #
# Les personnages — portée DÉRIVÉE de leurs apparitions
# --------------------------------------------------------------------------- #
def test_un_personnage_suit_ses_apparitions(client, db_path, deux_albums, derriere_proxy):
    """Décision du 2026-08-27 : ce n'est pas une mesure de confidentialité (la sauvegarde
    reste ouverte) mais d'USAGE — l'autocomplétion doit rester à la taille de l'étude."""
    from conftest import ADMIN
    ici = client.post("/api/personnages", json={"nom": "Ici"}, headers=ADMIN).json()
    ailleurs = client.post("/api/personnages", json={"nom": "Ailleurs"}, headers=ADMIN).json()
    client.put(f"/api/regions/{deux_albums['r1']['id']}/locuteur",
               json={"personnage_id": ici["id"]}, headers=ADMIN)
    client.put(f"/api/regions/{deux_albums['r2']['id']}/locuteur",
               json={"personnage_id": ailleurs["id"]}, headers=ADMIN)

    _ouvrir(db_path, deux_albums["c1"], "bob")
    h = {"Remote-User": "bob"}
    noms = {p["nom"] for p in client.get("/api/personnages", headers=h).json()}
    assert noms == {"Ici"}
    assert client.get(f"/api/personnages/{ailleurs['id']}/alignements",
                      headers=h).status_code == 404


def test_un_personnage_sans_apparition_reste_visible(client, db_path, deux_albums,
                                                     derriere_proxy):
    """L'exception qui rend le geste possible : sans elle, le personnage qu'on vient de
    créer disparaîtrait avant qu'on ait pu lui attribuer une bulle."""
    _ouvrir(db_path, deux_albums["c1"], "bob", niveau="ecriture")
    h = {"Remote-User": "bob"}
    neuf = client.post("/api/personnages", json={"nom": "Tout neuf"}, headers=h).json()
    noms = {p["nom"] for p in client.get("/api/personnages", headers=h).json()}
    assert "Tout neuf" in noms
    assert client.get(f"/api/personnages/{neuf['id']}/alignements",
                      headers=h).status_code == 200


# --------------------------------------------------------------------------- #
# L'annulation est PERSONNELLE
# --------------------------------------------------------------------------- #
def test_on_n_annule_que_ses_propres_actes(client, db_path, deux_albums, derriere_proxy):
    """Ctrl+Z est un geste personnel. Le filtre est par AGENT et non par collection : la
    cible d'une suppression n'existe plus, donc un filtre par album rendrait impossible
    l'annulation d'une suppression — l'inverse du service rendu."""
    _ouvrir(db_path, deux_albums["c1"], "bob", niveau="ecriture")
    _ouvrir(db_path, deux_albums["c1"], "carol", niveau="ecriture")
    bob = {"Remote-User": "bob"}
    client.put(f"/api/regions/{deux_albums['r1']['id']}", json={"ocr_texte": "de bob"},
               headers=bob)
    # carol ne voit rien à annuler : l'acte est celui de bob
    assert client.get("/api/undo/prochain", headers={"Remote-User": "carol"}).json() is None
    assert client.post("/api/undo", headers={"Remote-User": "carol"}).status_code == 404
    # bob, lui, retrouve le sien
    assert client.get("/api/undo/prochain", headers=bob).json() is not None
    assert client.post("/api/undo", headers=bob).status_code == 200


# --------------------------------------------------------------------------- #
# Portée à PLUSIEURS collections — l'agrégation, pas seulement le filtrage
# --------------------------------------------------------------------------- #
def test_plusieurs_collections_lues_s_additionnent(client, db_path, deux_albums,
                                                   derriere_proxy, png_bytes):
    """Tous les autres tests n'ouvrent qu'UNE collection, si bien qu'ils ne distinguent pas
    « filtre correctement » de « ne renvoie que la première ». Ici bob en lit deux, non
    contiguës (c1 et c3, pas c2) : les compteurs doivent AGRÉGER les deux et exclure la
    troisième.

    Ce que ce test ne prouve PAS, contrairement à ce que j'ai d'abord écrit ici : il
    n'attrape pas une inversion entre les paramètres de `clause_album` et ceux de
    `clause_terme`. Les deux lient la MÊME liste (les collections lues), donc les échanger
    est sans effet observable. Éprouvé par mutation le 2026-08-27 — il attrape en revanche
    un compteur qu'on aurait oublié de filtrer.
    """
    from conftest import ADMIN
    import sqlite3

    # Un troisième album dans une troisième collection, lisible lui aussi.
    a3 = client.post("/api/albums", json={"titre": "Troisième"}, headers=ADMIN).json()
    pl3 = client.post(f"/api/albums/{a3['id']}/import", headers=ADMIN,
                      files={"file": ("p.png", png_bytes, "image/png")}).json()
    r3 = client.post(f"/api/planches/{pl3['id']}/regions", headers=ADMIN,
                     json={"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9}).json()
    conn = sqlite3.connect(db_path)
    try:
        c3 = conn.execute("INSERT INTO collection (nom) VALUES ('Étude C')").lastrowid
        conn.execute("DELETE FROM collection_album WHERE album_id = ?", (a3["id"],))
        conn.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                     (c3, a3["id"]))
        conn.commit()
    finally:
        conn.close()

    # Le même tag posé dans les TROIS albums ; bob lit c1 et c3, pas c2.
    for rid in (deux_albums["r1"]["id"], deux_albums["r2"]["id"], r3["id"]):
        client.put(f"/api/regions/{rid}/annotation",
                   json={"note": "", "tags": ["partout"]}, headers=ADMIN)
    _ouvrir(db_path, deux_albums["c1"], "bob")
    _ouvrir(db_path, c3, "bob")
    h = {"Remote-User": "bob"}

    freq = {t["label"]: t["frequence"] for t in client.get("/api/tags", headers=h).json()}
    assert freq["partout"] == 2          # c1 + c3, jamais c2

    c = client.get("/api/corpus", headers=h).json()
    assert c["albums"] == 2 and c["planches"] == 2

    lex = client.get("/api/lexique", headers=h).json()
    assert {t["label"]: t["frequence"] for t in lex["tags"]}["partout"] == 2


# --------------------------------------------------------------------------- #
# Voir n'est pas changer — la faille trouvée en relisant le 2026-08-27
# --------------------------------------------------------------------------- #
# Dix-neuf routes d'écriture ne portaient qu'une garde de LECTURE : les accesseurs
# `_get_valeur` / `_get_dimension` / `_get_domaine` / `_get_personnage` répondent « peux-tu
# le voir », pas « peux-tu le changer ». La suite était verte, le cliquet aussi — il prouve
# qu'une route consulte la portée, jamais qu'elle en tire la bonne conclusion.
@pytest.fixture
def lecteur(client, db_path, deux_albums, derriere_proxy):
    """Bob, en LECTURE SEULE sur la première collection. Il voit, il ne touche pas."""
    _ouvrir(db_path, deux_albums["c1"], "bob", niveau="lecture")
    return {"Remote-User": "bob"}


def _un_terme(client, db_path):
    """Un domaine, une dimension et une valeur GLOBAUX, montés par un administrateur."""
    from conftest import ADMIN
    dom = client.post("/api/domaines", json={"nom": "emotions"}, headers=ADMIN).json()
    dim = client.post("/api/attributs/dimensions",
                      json={"cible": "case", "nom": "ton"}, headers=ADMIN).json()
    val = client.post(f"/api/attributs/dimensions/{dim['id']}/valeurs",
                      json={"valeur": "grave"}, headers=ADMIN).json()
    return dom, dim, val


def test_lecture_seule_ne_modifie_pas_le_vocabulaire(client, db_path, deux_albums, lecteur):
    """403 : le terme est bien VISIBLE (il vient d'être listé), donc un 404 mentirait.
    Le refus parle des droits de l'appelant et ne fuit rien."""
    dom, dim, val = _un_terme(client, db_path)
    assert client.get("/api/domaines", headers=lecteur).status_code == 200   # il les voit
    assert client.patch(f"/api/domaines/{dom['id']}",
                        json={"nom": "autre"}, headers=lecteur).status_code == 403
    assert client.delete(f"/api/domaines/{dom['id']}", headers=lecteur).status_code == 403
    assert client.delete(f"/api/attributs/dimensions/{dim['id']}",
                         headers=lecteur).status_code == 403
    assert client.put(f"/api/attributs/valeurs/{val['id']}",
                      json={"valeur": "x"}, headers=lecteur).status_code == 403
    assert client.patch(f"/api/attributs/valeurs/{val['id']}/lexique",
                        json={"definition": "d"}, headers=lecteur).status_code == 403


def test_lecture_seule_ne_touche_pas_au_registre_des_personnages(client, lecteur):
    from conftest import ADMIN
    p = client.post("/api/personnages", json={"nom": "Tintin"}, headers=ADMIN).json()
    assert client.post("/api/personnages", json={"nom": "Milou"},
                       headers=lecteur).status_code == 403
    assert client.put(f"/api/personnages/{p['id']}", json={"nom": "X"},
                      headers=lecteur).status_code == 403
    assert client.delete(f"/api/personnages/{p['id']}", headers=lecteur).status_code == 403


def test_lecture_seule_n_ajoute_pas_de_paternite(client, deux_albums, lecteur):
    """404 et non 403, ici : une contribution porte sur un ALBUM, et les données suivent
    la doctrine « hors portée = introuvable »."""
    r = client.post(f"/api/albums/{deux_albums['a1']['id']}/contributions",
                    json={"nom": "Hergé", "role": "scenariste"}, headers=lecteur)
    assert r.status_code == 404


def test_on_ne_range_pas_son_vocabulaire_chez_les_autres(client, db_path, deux_albums,
                                                         derriere_proxy):
    """Changer la PORTÉE d'un terme, c'est le déplacer chez quelqu'un. Il faut donc écrire
    dans la collection VISÉE, pas seulement dans la sienne."""
    from conftest import ADMIN
    dom, dim, val = _un_terme(client, db_path)
    _ouvrir(db_path, deux_albums["c1"], "bob", niveau="ecriture")
    h = {"Remote-User": "bob"}
    # sa propre collection : accepté
    assert client.patch(f"/api/attributs/valeurs/{val['id']}/lexique",
                        json={"collection_id": deux_albums["c1"]},
                        headers=h).status_code == 200
    # celle d'à côté : introuvable
    assert client.patch(f"/api/attributs/valeurs/{val['id']}/lexique",
                        json={"collection_id": deux_albums["c2"]},
                        headers=h).status_code == 404


def test_lecture_seule_ne_saborde_pas_un_lot_ni_n_annule(client, db_path, deux_albums,
                                                         lecteur):
    """Annuler un lot INTERROMPT un traitement, et Ctrl+Z rejoue une écriture : ni l'un ni
    l'autre n'est une lecture."""
    import pipeline.jobs as jobs_mod
    jobs_mod._jobs[7] = {"id": 7, "passes": ["ocr"],
                         "planche_ids": [deux_albums["pl1"]["id"]],
                         "total": 1, "done": 0, "current": None,
                         "errors": [], "status": "en_cours", "cancel": False}
    assert client.get("/api/jobs/7", headers=lecteur).status_code == 200   # il le voit
    assert client.post("/api/jobs/7/annuler", headers=lecteur).status_code == 404
    assert client.post("/api/undo", headers=lecteur).status_code == 403


def test_un_objet_partage_n_expose_pas_le_vocabulaire_prive(client, db_path, deux_albums,
                                                            derriere_proxy):
    """Un personnage traverse les albums : si ses attributs n'étaient pas filtrés, il
    exposerait la grille d'analyse d'une autre étude — pas seulement un mot.

    Écart trouvé en relisant : `GET /api/attributs/valeurs` masquait déjà ces termes, mais
    on les retrouvait par `GET /api/personnages/{id}/attributs`.
    """
    from conftest import ADMIN
    import sqlite3
    perso = client.post("/api/personnages", json={"nom": "Partagé"}, headers=ADMIN).json()
    client.put(f"/api/regions/{deux_albums['r1']['id']}/locuteur",
               json={"personnage_id": perso["id"]}, headers=ADMIN)
    dim = client.post("/api/attributs/dimensions",
                      json={"cible": "personnage", "nom": "grille"}, headers=ADMIN).json()
    prive = client.post(f"/api/attributs/dimensions/{dim['id']}/valeurs",
                        json={"valeur": "secret"}, headers=ADMIN).json()
    public = client.post(f"/api/attributs/dimensions/{dim['id']}/valeurs",
                         json={"valeur": "connu"}, headers=ADMIN).json()
    for v in (prive["id"], public["id"]):
        client.put(f"/api/personnages/{perso['id']}/attributs",
                   json={"valeur_id": v}, headers=ADMIN)
    conn = sqlite3.connect(db_path)          # « secret » devient local à la collection 2
    try:
        conn.execute("UPDATE attribut_valeur SET collection_id = ? WHERE id = ?",
                     (deux_albums["c2"], prive["id"]))
        conn.commit()
    finally:
        conn.close()

    _ouvrir(db_path, deux_albums["c1"], "bob")
    h = {"Remote-User": "bob"}
    # bob VOIT le personnage (il parle dans sa collection)…
    assert client.get(f"/api/personnages/{perso['id']}/attributs",
                      headers=h).status_code == 200
    vus = {a["valeur"] for a in
           client.get(f"/api/personnages/{perso['id']}/attributs", headers=h).json()}
    assert vus == {"connu"}                  # …mais pas la grille d'à côté


def test_moi_dit_pourquoi_on_ne_voit_rien(client, deux_albums, derriere_proxy):
    """Une portée vide rend l'application VISUELLEMENT indistinguable d'un corpus vide.
    C'est la bonne réponse de sécurité — 404 partout, rien ne fuit — et la pire réponse
    d'usage : on se croit devant un outil cassé alors qu'il manque un droit.

    Le compte renvoyé est celui de l'APPELANT, pas celui du corpus : il ne révèle rien.
    """
    seul = client.get("/api/moi", headers={"Remote-User": "bob"}).json()
    # Sous-ensemble, et non égalité : le bloc s'est enrichi depuis (AUTH-4 y ajoute le
    # référent d'instance et les noms des groupes d'administration). Figer le dict entier
    # ferait échouer ce test à chaque ajout, pour une raison qui n'est pas la sienne.
    garde = ("total", "admin", "collections", "ecriture")
    assert {k: seul["acces"][k] for k in garde} == {
        "total": False, "admin": False, "collections": 0, "ecriture": 0}


def test_moi_compte_les_acces_accordes(client, db_path, deux_albums, derriere_proxy):
    _ouvrir(db_path, deux_albums["c1"], "bob", niveau="ecriture")
    a = client.get("/api/moi", headers={"Remote-User": "bob"}).json()["acces"]
    assert a["collections"] == 1 and a["ecriture"] == 1 and not a["total"]
    admin = client.get("/api/moi", headers={"Remote-User": "root",
                                            "Remote-Groups": "bd-admins"}).json()["acces"]
    assert admin["total"] and admin["admin"] and admin["collections"] is None


# --------------------------------------------------------------------------- #
# « Aucun groupe » recouvrait deux situations (AUTH-8)
#
# `groupes()` fait `headers.get("Remote-Groups") or ""` : un en-tête ABSENT et un en-tête
# VIDE y arrivent identiques. Pour une LISTE c'est correct — dans les deux cas il n'y en a
# aucun. Mais l'un veut dire « les groupes ne sont pas recopiés », ce qui rend TOUS les
# accès par groupe silencieusement inopérants, et l'autre « ce compte n'appartient à aucun
# groupe », qui n'appelle aucune réparation. Le même écran vide les confondait.
# --------------------------------------------------------------------------- #
def test_moi_distingue_l_entete_de_groupes_absent_de_l_entete_vide(client, derriere_proxy):
    """Et `groupes` rend la MÊME chose dans les deux cas : c'est bien ce qu'on lui demande.

    Le test le vérifie explicitement, parce que c'est la condition posée par AUTH-8 — la
    différence voyage à part, et un appelant qui ignore le nouveau champ continue de se
    comporter exactement comme avant.
    """
    absent = client.get("/api/moi", headers={"Remote-User": "bob"}).json()
    vide = client.get("/api/moi", headers={"Remote-User": "bob",
                                           "Remote-Groups": ""}).json()
    plein = client.get("/api/moi", headers={"Remote-User": "bob",
                                            "Remote-Groups": "linguistes"}).json()

    assert absent["acces"]["entete_groupes"] is False
    assert vide["acces"]["entete_groupes"] is True
    assert plein["acces"]["entete_groupes"] is True

    assert absent["groupes"] == vide["groupes"] == [], (
        "le contrat de `groupes()` ne change pas : une liste, vide dans les deux cas")
    assert plein["groupes"] == ["linguistes"]


def test_hors_proxy_la_question_des_groupes_ne_se_pose_pas(client):
    """`null` et non `False` — sans `BD_AUTH_PROXY`, aucun en-tête n'est LU.

    La distinction compte : `False` signifie « il manque alors qu'il aurait dû venir »,
    c'est-à-dire une panne à réparer. En mono-poste il n'y a ni proxy ni groupes, et
    annoncer une panne de recopie y serait un diagnostic inventé — le travers exact que ce
    chantier ferme. Aucune des deux situations nouvelles ne peut donc y apparaître.

    Pas de fixture `derriere_proxy` ici, et c'est le sujet du test : les en-têtes envoyés
    sont ignorés, précisément parce qu'un client qui atteindrait l'app en direct pourrait
    sinon se déclarer qui il veut.
    """
    for entetes in ({}, {"Remote-User": "bob"}, {"Remote-User": "bob",
                                                 "Remote-Groups": "bd-admins"}):
        d = client.get("/api/moi", headers=entetes).json()
        assert d["acces"]["entete_groupes"] is None, entetes
        assert d["groupes"] == [], entetes


# --------------------------------------------------------------------------- #
# Relecture des filtres de LECTURE (AUTH-2, dernier bloc)
#
# Le cliquet ci-dessus prouve qu'une route CONSULTE la portée, jamais qu'elle en tire la
# bonne conclusion. Ce bloc vient d'une relecture ligne à ligne des routes de liste, et non
# d'une suite rouge : tout passait au vert. Un seul défaut, sous trois formes — un terme du
# vocabulaire pouvait être plus GLOBAL que celui dont il dépend, et c'est le NOM du parent
# qui fuyait (un axe d'analyse, pas un mot).
# --------------------------------------------------------------------------- #
def _portee_du_terme(db_path, table, oid):
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(f"SELECT collection_id FROM {table} WHERE id = ?",
                            (oid,)).fetchone()[0]
    finally:
        conn.close()


def _terme_local(client, db_path, collection_id):
    """Décor commun : un domaine et une dimension LOCAUX à `collection_id`, plus une
    valeur créée par l'API sous cette dimension — laquelle doit HÉRITER de la portée de
    sa dimension. Avant v24 elle naissait globale : l'import de vocabulaire posait bien
    `collection_id`, les routes de création jamais."""
    from conftest import ADMIN
    dom = client.post("/api/domaines", json={"nom": "affects prives"},
                      headers=ADMIN).json()
    client.patch(f"/api/domaines/{dom['id']}/lexique",
                 json={"collection_id": collection_id}, headers=ADMIN)
    dim = client.post("/api/attributs/dimensions",
                      json={"cible": "case", "nom": "tension secrete",
                            "domaine_id": dom["id"]}, headers=ADMIN).json()
    client.patch(f"/api/attributs/dimensions/{dim['id']}/lexique",
                 json={"collection_id": collection_id}, headers=ADMIN)
    val = client.post(f"/api/attributs/dimensions/{dim['id']}/valeurs",
                      json={"valeur": "palpable"}, headers=ADMIN).json()
    return dom, dim, val


def test_valeur_creee_herite_la_portee_de_sa_dimension(client, db_path, deux_albums,
                                                       derriere_proxy):
    """Un terme ne peut pas être plus GLOBAL que le terme dont il dépend.

    `POST .../valeurs` n'a jamais posé de `collection_id` : la valeur naissait globale,
    donc visible de tous, alors que sa dimension pouvait être locale à une étude. Le
    dommage n'est pas la valeur (« palpable » ne dit rien) mais ce qu'elle TRAÎNE : les
    routes à plat renvoient `dimension` — le nom de l'axe d'analyse d'à côté.
    """
    _ouvrir(db_path, deux_albums["c1"], "bob")
    _, dim, val = _terme_local(client, db_path, deux_albums["c2"])
    # L'héritage se lit dans la LIGNE STOCKÉE, et il faut le vérifier là. Se contenter de
    # l'absence dans la liste ci-dessous laisserait passer une régression : le filtre
    # parent masque déjà ce cas, si bien que retirer l'héritage garde la suite verte.
    assert _portee_du_terme(db_path, "attribut_valeur", val["id"]) == deux_albums["c2"]
    plat = client.get("/api/attributs/valeurs", headers={"Remote-User": "bob"}).json()
    assert not [v for v in plat if v["id"] == val["id"]]
    assert "tension secrete" not in {v["dimension"] for v in plat}


def test_dimension_creee_herite_la_portee_de_son_domaine(client, db_path, deux_albums,
                                                         derriere_proxy):
    """Même règle un cran plus haut, et la fuite y est plus directe : `GET
    /api/attributs/dimensions` renvoyait le NOM du domaine sans le filtrer, si bien
    qu'une dimension globale rattachée à un domaine privé le nommait à tout le monde."""
    _ouvrir(db_path, deux_albums["c1"], "bob")
    from conftest import ADMIN
    dom = client.post("/api/domaines", json={"nom": "domaine prive"},
                      headers=ADMIN).json()
    client.patch(f"/api/domaines/{dom['id']}/lexique",
                 json={"collection_id": deux_albums["c2"]}, headers=ADMIN)
    dim = client.post("/api/attributs/dimensions",
                      json={"cible": "case", "nom": "axe herite",
                            "domaine_id": dom["id"]}, headers=ADMIN).json()
    assert _portee_du_terme(db_path, "attribut_dimension",
                            dim["id"]) == deux_albums["c2"]
    dims = client.get("/api/attributs/dimensions",
                      headers={"Remote-User": "bob"}).json()
    assert "domaine prive" not in {d["domaine"] for d in dims}
    assert "axe herite" not in {d["nom"] for d in dims}


def test_resume_du_lexique_ne_compte_que_le_vocabulaire_visible(client, db_path,
                                                                deux_albums,
                                                                derriere_proxy):
    """Les quatre requêtes de `GET /api/lexique` étaient filtrées ; son `resume` ne
    l'était pas. Le panneau affichait donc « 3 définis sur 41 termes » à qui n'en voit
    que trois — le total DIT le volume de vocabulaire des autres, et le pourcentage
    devient faux pour la personne qui le lit."""
    _ouvrir(db_path, deux_albums["c1"], "bob")
    _terme_local(client, db_path, deux_albums["c2"])
    lex = client.get("/api/lexique", headers={"Remote-User": "bob"}).json()
    vus = (len(lex["domaines"]) + len(lex["dimensions"]) + len(lex["tags"])
           + sum(len(d["valeurs"]) for d in lex["dimensions"]))
    assert lex["resume"]["total"] == vus


def test_terme_incoherent_deja_en_base_reste_masque(client, db_path, deux_albums,
                                                    derriere_proxy):
    """L'héritage ci-dessus empêche d'en CRÉER ; il ne répare pas ce qui existe.

    Une base antérieure à v24 contient exactement la situation en cause — les routes de
    création n'y posaient aucun `collection_id`. Ce test la fabrique par SQL direct,
    seule façon honnête de justifier le filtre parent côté lecture : sans lui, la
    correction ne vaudrait que pour les bases neuves.
    """
    import sqlite3
    from conftest import ADMIN
    _ouvrir(db_path, deux_albums["c1"], "bob")
    dim = client.post("/api/attributs/dimensions",
                      json={"cible": "case", "nom": "axe legacy"}, headers=ADMIN).json()
    val = client.post(f"/api/attributs/dimensions/{dim['id']}/valeurs",
                      json={"valeur": "vestige"}, headers=ADMIN).json()
    conn = sqlite3.connect(db_path)
    try:                                    # dimension privée, valeur restée globale
        conn.execute("UPDATE attribut_dimension SET collection_id = ? WHERE id = ?",
                     (deux_albums["c2"], dim["id"]))
        conn.execute("UPDATE attribut_valeur SET collection_id = NULL WHERE id = ?",
                     (val["id"],))
        conn.commit()
    finally:
        conn.close()
    h = {"Remote-User": "bob"}
    plat = client.get("/api/attributs/valeurs", headers=h).json()
    assert "axe legacy" not in {v["dimension"] for v in plat}
    # …et par la bande, via un objet partagé : la même valeur affectée à une région
    # lisible nommerait l'axe d'à côté.
    client.put(f"/api/regions/{deux_albums['r1']['id']}/attributs",
               json={"valeur_id": val["id"]}, headers=ADMIN)
    attrs = client.get(f"/api/regions/{deux_albums['r1']['id']}/attributs",
                       headers=h).json()
    assert "axe legacy" not in {a["dimension"] for a in attrs}


# --------------------------------------------------------------------------- #
# Migration v23 → v24
# --------------------------------------------------------------------------- #
def test_migration_v23_vers_v24_recolle_la_portee_des_termes(tmp_path):
    """La ceinture côté lecture MASQUE le terme incohérent ; elle ne le répare pas, et le
    « % défini » continue de le compter (il compte par appartenance). L'étape v24 fait
    descendre la portée du domaine vers ses dimensions, puis vers leurs valeurs.

    Deux témoins vérifient qu'elle ne déborde pas : un terme déjà local à une AUTRE
    collection est un fait délibéré, et un terme sous un parent global reste global.
    """
    import sqlite3
    import database
    db = tmp_path / "pre24.sqlite"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE albums (id INTEGER PRIMARY KEY, titre TEXT);"
        "CREATE TABLE planches (id INTEGER PRIMARY KEY, album_id INTEGER);"
        "CREATE TABLE domaine (id INTEGER PRIMARY KEY, collection_id INTEGER);"
        "CREATE TABLE attribut_dimension (id INTEGER PRIMARY KEY, domaine_id INTEGER,"
        "                                 collection_id INTEGER);"
        "CREATE TABLE attribut_valeur (id INTEGER PRIMARY KEY, dimension_id INTEGER,"
        "                              collection_id INTEGER);"
        # domaine 1 local à la collection 7 ; domaine 2 global
        "INSERT INTO domaine (id, collection_id) VALUES (1, 7), (2, NULL);"
        # dim 10 : à recoller · dim 11 : déjà ailleurs · dim 12 : parent global
        "INSERT INTO attribut_dimension (id, domaine_id, collection_id) "
        "     VALUES (10, 1, NULL), (11, 1, 9), (12, 2, NULL);"
        "INSERT INTO attribut_valeur (id, dimension_id, collection_id) "
        "     VALUES (100, 10, NULL), (101, 11, NULL), (102, 12, NULL);"
        "PRAGMA user_version = 23;")
    conn.commit()
    database._migrate(conn)
    dims = dict(conn.execute("SELECT id, collection_id FROM attribut_dimension"))
    vals = dict(conn.execute("SELECT id, collection_id FROM attribut_valeur"))
    assert dims == {10: 7, 11: 9, 12: None}
    assert vals == {100: 7, 101: 9, 102: None}   # 100 recollé EN CASCADE, via sa dimension
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    conn.close()


# --------------------------------------------------------------------------- #
# Sauvegarde — la décision du 2026-08-27 rejouée par DROIT-1
# --------------------------------------------------------------------------- #
def test_la_sauvegarde_est_reservee_aux_administrateurs(client, deux_albums,
                                                        derriere_proxy):
    """Elle déverse la base ENTIÈRE, toutes collections confondues.

    L'arbitrage du 2026-08-27 la laissait ouverte à tout compte et portait sa propre
    CONDITION DE RÉOUVERTURE : « dès qu'un tiering de droits est effectif (DROIT-1), cette
    décision se rejoue. » Elle s'est déclenchée le 2026-08-28.

    L'argument d'origine tient : une sauvegarde partielle ne restaure pas une instance. On
    ne la scope donc pas — elle reste ENTIÈRE et change de public. Sauvegarder est un geste
    d'exploitation, pas de recherche.
    """
    from conftest import ADMIN
    r = client.get("/api/sauvegarde", headers={"Remote-User": "bob"})
    assert r.status_code == 403 and "administrateurs" in r.json()["detail"]
    assert client.post("/api/sharedocs/deposer-sauvegarde", json={"dossier": "x"},
                       headers={"Remote-User": "bob"}).status_code == 403
    assert client.get("/api/sauvegarde", headers=ADMIN).status_code == 200


def test_le_mono_poste_garde_sa_sauvegarde(client):
    """Sans proxy, il n'y a personne à qui la refuser : le comportement d'avant est
    strictement conservé."""
    assert client.get("/api/sauvegarde").status_code == 200


# --------------------------------------------------------------------------- #
# AUTH-1 — l'accord inter-annotateurs parle de PERSONNES, pas du corpus
# --------------------------------------------------------------------------- #
def test_accord_inter_est_refuse_a_qui_ne_fait_que_lire(client, db_path, deux_albums,
                                                        derriere_proxy):
    """Le seul rapport d'analyse réservé, et pour une raison qui lui est propre : il NOMME
    (`auteurs`), il APPARIE (le taux d'accord de deux gens précis) et il CITE à la ligne
    près. Un lecteur seul — un étudiant, un partenaire, un relecteur externe — obtenait le
    relevé nominatif des erreurs de gens qui n'ont pas choisi d'être mesurés par lui.

    La règle retenue : ceux qui voient la mesure sont ceux qu'elle mesure.
    """
    _ouvrir(db_path, deux_albums["c1"], "bob", "lecture")
    r = client.get("/api/analyse/accord-inter", headers={"Remote-User": "bob"})
    assert r.status_code == 403
    # 403 et non 404 : la route est publique, c'est son CONTENU qui ne l'est pas — et le
    # refus doit se LIRE, sans quoi on rend le silence qu'AUTH-2 combat.
    assert "écrit" in r.json()["detail"]

    # Le voisin, lui, ne nomme personne : il reste ouvert en lecture.
    assert client.get("/api/analyse/accord",
                      headers={"Remote-User": "bob"}).status_code == 200


def test_accord_inter_s_ouvre_a_qui_ecrit(client, db_path, deux_albums, derriere_proxy):
    """Écrire suffit — inutile de posséder : les annotateurs doivent voir leur propre
    accord, c'est l'usage premier du rapport (qualité, arbitrage entre linguistes)."""
    _ouvrir(db_path, deux_albums["c1"], "bob", "ecriture")
    assert client.get("/api/analyse/accord-inter",
                      headers={"Remote-User": "bob"}).status_code == 200


def test_accord_inter_ne_porte_que_sur_ce_qu_on_ecrit(client, db_path, deux_albums,
                                                      derriere_proxy):
    """La portée du rapport suit le droit d'ÉCRIRE, pas celui de lire : un album qu'on lit
    sans y écrire ne livre pas les désaccords de ceux qui y travaillent."""
    import sqlite3
    _ouvrir(db_path, deux_albums["c1"], "bob", "ecriture")
    _ouvrir(db_path, deux_albums["c2"], "bob", "lecture")
    # Une re-touche inter-auteurs dans l'album qu'il LIT seulement (c2 / r2).
    conn = sqlite3.connect(db_path)
    try:
        cid = conn.execute(
            "INSERT INTO token_correction (region_id, ordre, forme, pos, auteur) "
            "VALUES (?, 0, 'MOT', 'VERB', 'carol')",
            (deux_albums["r2"]["id"],)).lastrowid
        for agent, pos, avant in (("alice", "NOUN", None), ("carol", "VERB", "NOUN")):
            conn.execute(
                "INSERT INTO evenement (type, agent, agent_type, cible_table, cible_id, "
                "avant, apres) VALUES ('modification', ?, 'humain', 'token_correction', "
                "?, ?, ?)",
                (agent, cid,
                 json.dumps({"lemme": "m", "pos": avant, "morph": ""}) if avant else None,
                 json.dumps({"lemme": "m", "pos": pos, "morph": ""})))
        conn.commit()
    finally:
        conn.close()

    r = client.get("/api/analyse/accord-inter",
                   headers={"Remote-User": "bob"}).json()
    assert r["auteurs"] == [], "un album qu'on LIT seulement ne doit rien livrer"
    assert r["retouches"] == 0


def test_un_lot_purge_n_est_visible_de_personne(client, db_path, deux_albums,
                                                derriere_proxy, monkeypatch):
    """CONC-1 — la purge fait de « job inconnu » l'état FINAL de tout lot.

    C'est la raison de l'ordre imposé par la fiche : avant le durcissement de
    `_job_visible`, un identifiant purgé aurait été APPROUVÉ par la garde
    (`set([]) <= autorisees`), et seul l'ordre des vérifications à chaque appel l'aurait
    rattrapé. Ce test relie les deux moitiés — ce que la purge produit, la garde le refuse
    — là où le test de la purge, lui, ne regarde que le registre.
    """
    import pipeline.jobs as jobs_mod
    from conftest import ADMIN

    # Registre de travail, restauré par `monkeypatch` quoi qu'il arrive : le `del`
    # ci-dessous est le chemin NOMINAL, et une assertion qui échoue avant lui laisserait
    # 4242 derrière elle. Un test qui pollue le suivant fait échouer un innocent.
    monkeypatch.setattr(jobs_mod, "_jobs", dict(jobs_mod._jobs))

    jobs_mod._jobs[4242] = {"id": 4242, "passes": ["ocr"],
                            "planche_ids": [deux_albums["pl1"]["id"]],
                            "total": 1, "done": 1, "current": None,
                            "errors": [], "status": "termine", "cancel": False}
    assert client.get("/api/jobs/4242", headers=ADMIN).status_code == 200

    del jobs_mod._jobs[4242]                                  # ce que la purge fera

    assert client.get("/api/jobs/4242", headers=ADMIN).status_code == 404
    assert client.post("/api/jobs/4242/annuler", headers=ADMIN).status_code == 404
    assert all(s["id"] != 4242 for s in client.get("/api/jobs", headers=ADMIN).json())


# --------------------------------------------------------------------------- #
# ANA-7 — les six exports d'analyse, face à la portée
# --------------------------------------------------------------------------- #
def _relire_un_token(db_path, region_id, auteur="admin"):
    """Pose une correction humaine sur le premier token d'une région.

    Sans elle, l'accord modèle↔humain n'a RIEN à compter : le rapport porte sur les tokens
    RELUS, et un décor sans relecture rendrait deux rapports vides — donc un test de portée
    qui passerait sans rien mesurer. C'est le piège que QA-6 a nommé, « un skip se lit
    comme un succès », transposé au décor plutôt qu'au moteur.
    """
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        t = conn.execute("SELECT ordre, texte, lemme, pos FROM tokens WHERE region_id = ? "
                         "ORDER BY ordre LIMIT 1", (region_id,)).fetchone()
        assert t is not None, (
            f"aucun token sur la région {region_id} : le décor ne porte rien à mesurer "
            "(spaCy absent ?), et le test de portée serait vide")
        conn.execute("INSERT INTO token_correction (region_id, ordre, forme, lemme, pos, "
                     "etat, auteur) VALUES (?, ?, ?, ?, ?, 'corrige', ?)",
                     (region_id, t[0], t[1], t[2], t[3], auteur))
        conn.commit()
    finally:
        conn.close()


# Les CINQ exports que ce décor suffit à distinguer. Le sixième, `accord-inter.csv`, a
# son propre test plus bas : son rapport ne lit qu'une chaîne de révision entre deux
# auteurs, qu'il faut poser dans le journal A3 — sans elle il est vide des DEUX côtés, et
# « identique » n'y prouverait rien.
EXPORTS_ANALYSE = [
    ("/api/analyse/frequences.csv", ""),
    # `motsecret` est dans les DEUX albums — c'est indispensable : un critère propre à
    # l'album autorisé ferait tester le FILTRE et non la portée, et le test passerait pour
    # une raison qui n'a rien à voir avec ce qu'il prétend garder. Mesuré : avec
    # `lemme=ici`, l'administrateur et bob recevaient le même fichier.
    ("/api/analyse/concordance.csv", "?lemme=motsecret"),
    ("/api/analyse/comparaison.csv", ""),
    ("/api/analyse/croisement.csv", "?axe_x=pos&axe_y=provenance"),
    ("/api/analyse/accord.csv", ""),
]


@pytest.mark.parametrize("chemin,quete", EXPORTS_ANALYSE)
def test_un_export_d_analyse_ne_rend_rien_hors_portee(client, db_path, deux_albums,
                                                      derriere_proxy, chemin, quete):
    """ANA-7 — six sorties neuves, et le cliquet ne dit PAS qu'elles concluent juste.

    `test_autorisation` exige qu'une route consulte la portée ; il ne vérifie jamais
    qu'elle en tire la bonne conclusion. Un export qui recalculerait ses filtres à côté de
    `_analyse_filtres` serait vert et fuirait. D'où ce test de COMPORTEMENT, sur les six.

    **Il est construit pour ne pas pouvoir passer à vide** : chaque cas exige d'abord de
    voir ce qui est AUTORISÉ avant de vérifier l'absence de ce qui ne l'est pas. Un décor
    muet — spaCy manquant, aucun token, aucune relecture — ferait échouer la première
    assertion au lieu de rendre la seconde triviale. C'est la leçon d'AUTH-5 : le mode
    d'échec d'un cliquet est le SEMIS, pas la garde.
    """
    from conftest import ADMIN
    _relire_un_token(db_path, deux_albums["r1"]["id"], "alice")
    _relire_un_token(db_path, deux_albums["r2"]["id"], "bob")

    admin = client.get(chemin + quete, headers=ADMIN)
    assert admin.status_code == 200, admin.text
    tout = admin.text
    assert tout.strip(), f"{chemin} ne rend rien même pour un administrateur : décor muet"

    _ouvrir(db_path, deux_albums["c1"], "bob", "ecriture")   # bob n'a QUE la collection 1
    h = {"Remote-User": "bob"}
    r = client.get(chemin + quete, headers=h)
    assert r.status_code == 200, r.text
    assert "Interdit" not in r.text, (
        f"{chemin} laisse fuir le TITRE d'un album hors portée")
    assert "ailleurs" not in r.text.lower(), (
        f"{chemin} laisse fuir un lemme d'un album hors portée")
    # L'ANTI-VACUITÉ, et ma première version était fausse : elle comparait des LONGUEURS,
    # or « 2 » et « 1 » font la même largeur — le croisement passait de 2 à 1 partout sans
    # que la chaîne change de taille. Une différence de CONTENU dit la même chose sans
    # supposer que filtrer raccourcisse.
    assert r.text != tout, (
        f"{chemin} rend exactement la même chose à bob qu'à l'administrateur : la portée "
        "n'a rien filtré, ou le décor ne distingue pas les deux albums")


def test_l_export_inter_herite_du_403_de_sa_route(client, db_path, deux_albums,
                                                  derriere_proxy):
    """ANA-7 — le refus est HÉRITÉ, pas réécrit.

    Un contrôle recopié dans l'export finirait par diverger de celui de la route JSON, et
    la divergence serait silencieuse : les deux réponses resteraient plausibles. Ici on
    vérifie qu'un compte qui LIT sans écrire nulle part reçoit le même 403 des deux côtés.
    """
    _ouvrir(db_path, deux_albums["c1"], "lecteur", "lecture")
    h = {"Remote-User": "lecteur"}
    assert client.get("/api/analyse/accord-inter", headers=h).status_code == 403
    assert client.get("/api/analyse/accord-inter.csv", headers=h).status_code == 403


def _chaine_de_revision(db_path, region_id, forme, lemme_a, lemme_b):
    """Deux annotateurs qui se relisent sur le MÊME token — la seule donnée que le rapport
    inter-annotateurs sache lire.

    Elle vit dans le journal A3 et non dans le modèle : celui-ci ne garde qu'UNE correction
    par token, si bien qu'une révision de plus efface la précédente. Le décor doit donc
    poser les deux ÉVÉNEMENTS, faute de quoi le rapport est vide — et un test de portée sur
    un rapport vide passerait des deux côtés sans rien prouver.
    """
    import json as _json
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        tc = conn.execute(
            "INSERT INTO token_correction (region_id, ordre, forme, lemme, pos, auteur) "
            "VALUES (?, 0, ?, ?, 'NOUN', 'bob')", (region_id, forme, lemme_b)).lastrowid
        for agent, lemme in (("alice", lemme_a), ("bob", lemme_b)):
            conn.execute(
                "INSERT INTO evenement (type, agent, agent_type, cible_table, cible_id, "
                "avant, apres) VALUES ('modification', ?, 'humain', 'token_correction', "
                "?, ?, ?)",
                (agent, tc, _json.dumps({"lemme": lemme_a, "pos": "NOUN", "morph": ""}),
                 _json.dumps({"lemme": lemme, "pos": "NOUN", "morph": ""})))
        conn.commit()
    finally:
        conn.close()


def test_l_export_inter_ne_cite_pas_une_divergence_hors_portee(client, db_path,
                                                               deux_albums, derriere_proxy):
    """ANA-7 — la SIXIÈME sortie, et la seule qui nomme des personnes.

    Les cinq autres se vérifient par un décor commun ; celle-ci exige une chaîne de
    révision entre deux auteurs, sans quoi son rapport est vide des deux côtés et
    « identique » ne prouverait rien. C'est précisément l'export dont le contenu compte le
    plus : il nomme, il apparie, et il cite à la ligne près.

    Le 403 hérité garde la PORTE ; ce test garde ce qui passe par elle — un annotateur qui
    écrit sur une collection ne doit pas lire les désaccords d'une autre équipe.
    """
    from conftest import ADMIN
    _chaine_de_revision(db_path, deux_albums["r1"]["id"], "ICI", "ici_a", "ici_b")
    _chaine_de_revision(db_path, deux_albums["r2"]["id"], "AILLEURS", "ail_a", "ail_b")

    tout = client.get("/api/analyse/accord-inter.csv", headers=ADMIN)
    assert tout.status_code == 200
    assert "ICI" in tout.text and "AILLEURS" in tout.text, (
        f"le décor ne produit pas deux divergences : {tout.text!r}")
    assert "alice" in tout.text and "bob" in tout.text, "l'export doit NOMMER (ANA-7)"

    _ouvrir(db_path, deux_albums["c1"], "bob", "ecriture")
    r = client.get("/api/analyse/accord-inter.csv", headers={"Remote-User": "bob"})
    assert r.status_code == 200, r.text
    assert "ICI" in r.text, "bob doit voir la divergence de SA collection"
    assert "AILLEURS" not in r.text, (
        "l'export inter cite une divergence d'une collection que bob n'écrit pas")
