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
    ("GET", "/annotation"): "idem (ANN-7, tranche 2) : chaque donnée vient d'une route /api gardée",
    ("GET", "/recherche"): "idem",
    ("GET", "/corpus"): "idem",
    ("GET", "/exploration"): "idem",
    ("GET", "/administration"): (
        "idem — et la coquille est ici une DÉCISION, pas une commodité (UX-10). Chaque "
        "bloc de cette page pose sa propre question : la liste des collections est "
        "filtrée par la portée, `GET /api/comptes-et-groupes` refuse les non-administrateurs, "
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
    ("GET", "/api/droits"): (
        "décrit le MODÈLE de droits en actes (AUTH-12, étape 3), identique pour tous et sans "
        "aucune donnée du corpus : la même réponse sur une instance vide. La table vit dans "
        "`autorisation.py` et aucune garde ne la lit ; « Mon compte » la lira aussi, pour une "
        "personne qui ne possède rien"),
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
    "/static": ("CSS/JS de l'application, et les illustrations FIXES de l'album de "
                "présentation (`static/wizard/`, UX-6) — aucune donnée de corpus"),
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


def test_groupe_admin_voit_tout(client, derriere_proxy):
    """Sur une instance sans bac à sable, la portée totale d'avant, NON bornée (COL-4 : elle
    ne se borne qu'aux bacs à sable, cf. `tests/test_bac_a_sable.py`)."""
    class Req:
        headers = {"Remote-User": "alice", "Remote-Groups": "bd-admins, autre"}
    import database
    conn = database.get_connection()
    try:
        p = autorisation.resoudre(conn, Req())
    finally:
        conn.close()
    assert p.tout and p.admin and p.utilisateur == "alice" and not p.bornee


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
        # COL-3, tranche 3c (F2) : un accès de collection suppose d'être du projet — ce
        # que la v38 fait de tout accès hors projet ; le décor le pose de même.
        conn.execute("INSERT OR IGNORE INTO projet_acces (projet_id, genre, principal, role) "
                     "SELECT p.id, ?, ?, 'membre' FROM collection c JOIN projet p "
                     "ON p.id = COALESCE(c.projet_id, (SELECT id FROM projet WHERE repli = 1)) "
                     "WHERE c.id = ? AND p.bac_a_sable_de IS NULL AND p.jeu = 0",
                     (genre, principal, collection_id))
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


def test_importer_une_planche_en_lecture_seule_est_refuse_par_le_serveur(
        client, db_path, data_dir, deux_albums, derriere_proxy, png_bytes):
    """UX-11 — la route d'import appelée DIRECTEMENT, sans l'écran, par un compte qui ne
    fait que LIRE la collection de l'album. La Bibliothèque ne lui offre pas le bouton
    (`ecrivable` faux), et ce n'est pas ce qui le protège : la garde est sur l'acte. C'est
    le seul test de ce chantier qui ne peut pas échouer en se fermant — une route ouverte
    se voit, un bouton masqué à tort non.

    404 et non 403 : l'album est lisible, mais une DONNÉE qu'on ne peut écrire répond
    « introuvable » (AUTH-2) — l'accesseur gardé en écriture ne distingue pas. Rien n'entre :
    ni planche en base, ni fichier dans `corpus/` ou `derivatives/`."""
    _ouvrir(db_path, deux_albums["c1"], "bob", niveau="lecture")
    h = {"Remote-User": "bob"}
    aid = deux_albums["a1"]["id"]
    assert client.get(f"/api/albums/{aid}/planches", headers=h).status_code == 200
    avant = sorted(p.as_posix() for p in data_dir.rglob("*") if p.is_file())
    r = client.post(f"/api/albums/{aid}/import", headers=h,
                    files={"file": ("p2.png", png_bytes, "image/png")})
    assert r.status_code == 404, r.text
    assert [p["id"] for p in client.get(f"/api/albums/{aid}/planches", headers=h).json()] \
        == [deux_albums["pl1"]["id"]]
    apres = sorted(p.as_posix() for p in data_dir.rglob("*") if p.is_file())
    assert [p for p in apres if "/corpus/" in p or "/derivatives/" in p] == \
        [p for p in avant if "/corpus/" in p or "/derivatives/" in p]
    # Le même geste, une fois l'écriture accordée, passe : le refus venait du niveau.
    _ouvrir(db_path, deux_albums["c1"], "bob", niveau="ecriture")
    r = client.post(f"/api/albums/{aid}/import", headers=h,
                    files={"file": ("p2.png", png_bytes, "image/png")})
    assert r.status_code == 201, r.text


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
    _case_export(db_path, deux_albums["c1"], "bob")   # DROIT-2 : sinon, le 403 de la porte
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
    # ANN-7 — le vocabulaire d'hier ne se compte plus, global ou local.
    assert "tags" not in c


@pytest.mark.parametrize("route", ["/api/export/json", "/api/export/csv", "/api/export/tei"])
def test_les_exports_n_exposent_pas_ce_que_l_ui_cache(client, db_path, deux_albums,
                                                      derriere_proxy, route):
    """Un export est une porte aussi large que l'UI, et plus discrète. Les trois
    sérialisations (JSON-LD, CSV, TEI) suivent la même règle que l'affichage."""
    _ouvrir(db_path, deux_albums["c1"], "bob")
    _case_export(db_path, deux_albums["c1"], "bob")   # DROIT-2 : sinon, le 403 de la porte
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


def _lignes_tags(db_path, region_id):
    """Les tags RÉELLEMENT posés sur une région, lus en base — pas ce que l'API montre.

    C'est la seule lecture qui distingue « rien ne s'est attaché » de « quelque chose
    s'est attaché et l'écran le cache » : les deux rendent `tags: []` à l'appelant, et
    c'est précisément l'écart que la garde ferme.
    """
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(
            "SELECT t.id, t.label, t.collection_id FROM annotation_tags at "
            "JOIN annotations an ON an.id = at.annotation_id "
            "JOIN tags t ON t.id = at.tag_id WHERE an.region_id = ?", (region_id,))]
    finally:
        conn.close()


def _case_export(db_path, collection_id, principal):
    """DROIT-2 — coche la case d'export d'un accès existant."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE collection_acces SET exporter = 1 WHERE collection_id = ? "
                     "AND principal = ?", (collection_id, principal))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def tag_illisible(client, db_path, deux_albums, derriere_proxy):
    """Une région que Bob lit, portant un tag GLOBAL et un tag LOCAL à la collection qu'il
    ne lit pas, plus un token pour que les surfaces d'analyse la voient. L'annotation est
    posée par un administrateur, AVANT l'accès de Bob : c'est l'état réel — un tag devenu
    local après avoir été posé, sur un album rangé ailleurs aussi."""
    import sqlite3
    from conftest import poser_tags
    # ANN-8 (2026-10-22) — un tag local ne se POSE plus hors de sa collection : l'état se
    # fabrique comme il naît, un tag global posé puis rendu local à c2. ANN-7 — aucune route
    # ne pose plus de tag : celui d'hier se pose en base, où les exports le lisent encore.
    r1 = deux_albums["r1"]["id"]
    poser_tags(db_path, r1, ["prive", "commun"])
    conn = sqlite3.connect(db_path)                      # APRÈS l'annotation : elle réindexe
    try:
        conn.execute("UPDATE tags SET collection_id = ? WHERE label = 'prive'",
                     (deux_albums["c2"],))
        conn.execute("INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
                     "VALUES (?, 0, 'DIS', 'dire', 'VERB', '')", (r1,))
        conn.commit()
    finally:
        conn.close()
    _ouvrir(db_path, deux_albums["c1"], "bob")
    # DROIT-2 — Bob EXPORTE c1 : ces tests éprouvent ce que les exports taisent, et sans
    # la case ils s'arrêteraient au 403 de la porte, avant d'avoir rien montré.
    _case_export(db_path, deux_albums["c1"], "bob")
    return {**deux_albums, "bob": {"Remote-User": "bob"}}


def _ranger_aussi(db_path, album_id, collection_id):
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                     (collection_id, album_id))
        conn.commit()
    finally:
        conn.close()


def test_le_csv_d_un_album_tait_un_tag_illisible(client, db_path, tag_illisible):
    """Lire l'album ne donne pas à lire tous les tags qu'il porte. L'export CSV d'un album
    a sa propre requête — il ne passe ni par la Recherche ni par l'Atelier.

    L'anti-vacuité a changé de forme le 2026-10-07 (AUTH-11). Elle disait « pour
    l'administrateur, le tag SORT » ; or l'album sort au titre de c1, et depuis ce jour
    son vocabulaire est celui de c1 quel que soit qui exporte — administrateur compris.
    Le tag sort donc là où il est chez lui : l'album rangé aussi dans c2, au titre de c2."""
    from conftest import ADMIN
    a1, c1, c2 = tag_illisible["a1"]["id"], tag_illisible["c1"], tag_illisible["c2"]
    _ranger_aussi(db_path, a1, c2)

    def fichier(h, collection_id):
        rep = client.get("/api/export/csv",
                         params={"album_id": a1, "collection_id": collection_id}, headers=h)
        assert rep.status_code == 200, rep.text
        return rep.text

    assert "prive" in fichier(ADMIN, c2)
    for qui in (ADMIN, tag_illisible["bob"]):
        vu = fichier(qui, c1)
        assert "commun" in vu and "prive" not in vu


def test_l_atelier_et_les_exports_d_album_taisent_un_tag_illisible(client, db_path,
                                                                   tag_illisible):
    """Le cœur `_annotation_selon`, qui sert les exports JSON et TEI d'un album (il servait
    aussi l'Atelier, jusqu'au basculement d'ANN-7, qui ne montre plus de tag).

    L'export porte ce que la COLLECTION emporte (AUTH-11, 2026-10-07) : au titre de c1,
    l'administrateur n'emporte pas le tag local à c2 ; au titre de c2 — l'album y étant
    rangé aussi —, il l'emporte. Et la route de l'annotation ne rend plus aucun tag."""
    from conftest import ADMIN
    r1, a1 = tag_illisible["r1"]["id"], tag_illisible["a1"]["id"]
    c1, c2 = tag_illisible["c1"], tag_illisible["c2"]
    _ranger_aussi(db_path, a1, c2)

    def lu(h, collection_id):
        ann = client.get(f"/api/regions/{r1}/annotation", headers=h).json()
        params = {"album_id": a1, "collection_id": collection_id}
        json_ = client.get("/api/export/json", params=params, headers=h)
        tei = client.get("/api/export/tei", params=params, headers=h)
        assert json_.status_code == 200 and tei.status_code == 200, (json_.text, tei.text)
        assert "tags" not in ann
        return json_.text, tei.text

    json_, tei = lu(ADMIN, c2)
    assert "prive" in json_ and "prive" in tei
    json_, tei = lu(ADMIN, c1)
    assert "commun" in json_ and "prive" not in json_
    assert "commun" in tei and "prive" not in tei
    json_, tei = lu(tag_illisible["bob"], c1)
    assert "commun" in json_ and "prive" not in json_
    assert "commun" in tei and "prive" not in tei


def test_annuler_une_note_ne_touche_aux_tags_d_hier_que_comme_la_route(client, db_path,
                                                                       tag_illisible):
    """Le piège d'hier entre l'Atelier et l'annulation — Ctrl+Z effaçait le tag qu'on ne
    voit pas — n'a plus d'objet : ANN-7, le basculement, l'annulation ne lit plus de tag.
    Elle fait ce que fait la route (`PUT …/annotation`) : rendre l'annotation à « sans
    note », c'est la vider, et elle part entière, avec ce qu'elle portait encore du
    vocabulaire d'hier — jusqu'à la migration qui retire ses tables."""
    from conftest import direct_query
    _ouvrir(db_path, tag_illisible["c1"], "bob", niveau="ecriture")
    bob, r1 = tag_illisible["bob"], tag_illisible["r1"]["id"]
    rep = client.put(f"/api/regions/{r1}/annotation", json={"note": "vu"}, headers=bob)
    assert rep.status_code == 200, rep.text
    rep = client.post("/api/undo", headers=bob)
    assert rep.status_code == 200, rep.text
    assert _lignes_tags(db_path, r1) == []
    assert not direct_query(db_path, "SELECT 1 FROM annotations WHERE region_id = ?", (r1,))


@pytest.fixture
def facettes_illisibles(client, db_path, deux_albums, derriere_proxy):
    """AUTH-11 — le décor des facettes qu'on ne lit pas. Sur une région que Bob lit : un
    locuteur qu'il voit. Sur la région qu'il ne lit pas : un locuteur qui n'apparaît que
    là. Plus un token, pour que les surfaces d'analyse voient la première. (Les valeurs
    d'attribut qui y étaient aussi sont parties avec le basculement d'ANN-7.)"""
    import sqlite3
    r1, r2 = deux_albums["r1"]["id"], deux_albums["r2"]["id"]
    conn = sqlite3.connect(db_path)
    try:
        vu = conn.execute("INSERT INTO personnages (nom) VALUES ('Visible')").lastrowid
        masque = conn.execute("INSERT INTO personnages (nom) VALUES ('Masque')").lastrowid
        conn.executemany("INSERT INTO bulle_locuteur (region_id, personnage_id) VALUES (?, ?)",
                         [(r1, vu), (r2, masque)])
        conn.execute("INSERT INTO tokens (region_id, ordre, texte, lemme, pos, morph) "
                     "VALUES (?, 0, 'DIS', 'dire', 'VERB', '')", (r1,))
        conn.commit()
    finally:
        conn.close()
    _ouvrir(db_path, deux_albums["c1"], "bob")
    return {"vu": vu, "masque": masque, "bob": {"Remote-User": "bob"}}


def _filtrer(client, route, extra, cle, ident, h):
    return client.get(route, params={**extra, cle: ident}, headers=h)


def test_une_facette_qu_on_ne_lit_pas_repond_comme_une_facette_absente(client,
                                                                        facettes_illisibles):
    """AUTH-11 — `_valider_facette` ne vérifiait que l'EXISTENCE : 404 pour un identifiant
    libre, 200 pour un locuteur qui n'apparaît que dans une collection qu'on ne lit pas
    (la valeur d'attribut, l'autre facette, est partie avec le basculement d'ANN-7).
    Énumérer les identifiants disait lesquels existent ailleurs — un oracle sans nom. Ce qu'on ne voit pas répond désormais EXACTEMENT comme
    ce qui n'existe pas, sur chacun des quatre cœurs qui valident leurs facettes.
    Anti-vacuité : l'administrateur passe, et Bob passe sur ce qu'il voit."""
    from conftest import ADMIN
    f = facettes_illisibles
    surfaces = [("/api/analyse/frequences", {}, ""),
                ("/api/analyse/concordance", {}, ""),
                ("/api/analyse/croisement", {"axe_x": "type", "axe_y": "pos"}, ""),
                ("/api/analyse/comparaison", {}, "a_"),
                ("/api/analyse/comparaison", {}, "b_")]
    facettes = [("personnage", f["masque"], f["vu"])]
    for route, extra, prefixe in surfaces:
        for cle, cachee, vue in facettes:
            quoi = (route, cle)
            assert _filtrer(client, route, extra, prefixe + cle, cachee,
                            ADMIN).status_code == 200, quoi
            assert _filtrer(client, route, extra, prefixe + cle, vue,
                            f["bob"]).status_code == 200, quoi
            illisible = _filtrer(client, route, extra, prefixe + cle, cachee, f["bob"])
            absente = _filtrer(client, route, extra, prefixe + cle, 999999, f["bob"])
            assert illisible.status_code == absente.status_code == 404, quoi
            assert illisible.json()["detail"] == absente.json()["detail"].replace(
                "999999", str(cachee)), quoi


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


# --------------------------------------------------------------------------- #
# ANN-6 — attribuer un locuteur : l'accesseur EN ÉCRITURE passe avant la garde de type
# --------------------------------------------------------------------------- #
def _case_dans(client, planche):
    from conftest import ADMIN
    r = client.post(f"/api/planches/{planche['id']}/regions", headers=ADMIN,
                    json={"type": "case", "x": 20, "y": 20, "w": 50, "h": 50})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _traces_de_locuteur(db_path):
    """(lignes de `bulle_locuteur`, événements qui la visent) — ce qu'un refus doit laisser à zéro."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        return (conn.execute("SELECT COUNT(*) FROM bulle_locuteur").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM evenement "
                             "WHERE cible_table = 'bulle_locuteur'").fetchone()[0])
    finally:
        conn.close()


QUI_N_ECRIT_PAS = {
    "lectrice": {"Remote-User": "lea"},      # lit la collection de l'album, sans y écrire
    "etrangere": {"Remote-User": "zoe"},     # ÉCRIT dans l'autre collection, ne lit pas celle-ci
    "anonyme": {},                           # derrière le proxy, sans identité : portée vide
}


@pytest.mark.parametrize("type_zone", ["bulle", "case"])
@pytest.mark.parametrize("qui", list(QUI_N_ECRIT_PAS))
def test_poser_un_locuteur_sans_ecrire_la_region_repond_introuvable(
        client, db_path, deux_albums, derriere_proxy, qui, type_zone):
    """404, sur une bulle COMME sur une case — jamais 422, jamais 200 — et rien d'écrit.

    Deux fautes que la suite entière laissait passer, mesurées par la relecture croisée du
    2026-10-12 (1 636 passés sous chacune) :

    - la garde de type AVANT l'accesseur : une étrangère ou un anonyme reçoit un 422 qui
      NOMME le type d'une région qu'il ne lit pas. « 404, jamais 403 » existe pour que
      l'absence soit la seule réponse — un 422 la trahit autant qu'un 403 ;
    - l'accesseur en LECTURE : une lectrice pose un locuteur, 200.

    Le premier se voit sur la case, le second sur la bulle : d'où les deux types. Le corps
    du refus est comparé à celui d'une région qui N'EXISTE PAS — c'est la seule façon de
    dire qu'il ne fuit rien, plutôt que de lister les mots qu'il ne devrait pas contenir.
    """
    from conftest import ADMIN
    _ouvrir(db_path, deux_albums["c1"], "lea")                       # lecture
    _ouvrir(db_path, deux_albums["c2"], "zoe", niveau="ecriture")    # écrit AILLEURS
    cible = {"bulle": deux_albums["r1"]["id"],
             "case": _case_dans(client, deux_albums["pl1"])}[type_zone]
    perso = client.post("/api/personnages", json={"nom": "Narrateur"}, headers=ADMIN).json()["id"]
    assert _traces_de_locuteur(db_path) == (0, 0)

    h = QUI_N_ECRIT_PAS[qui]
    rep = client.put(f"/api/regions/{cible}/locuteur", json={"personnage_id": perso}, headers=h)
    assert rep.status_code == 404, f"{qui}, région « {type_zone} » : {rep.status_code} {rep.text}"
    absente = client.put("/api/regions/987654/locuteur", json={"personnage_id": perso}, headers=h)
    assert absente.status_code == 404
    assert rep.json()["detail"] == absente.json()["detail"].replace("987654", str(cible)), (
        "le refus ne se lit pas comme celui d'une région absente : il dit quelque chose "
        "de celle-ci")
    assert _traces_de_locuteur(db_path) == (0, 0)


def test_qui_ecrit_la_region_recoit_la_reponse_de_la_garde(client, db_path, deux_albums,
                                                           derriere_proxy):
    """Le témoin du test ci-dessus : dans le MÊME décor, qui écrit dans la collection reçoit
    200 sur la bulle et le 422 nommé sur la case. Sans lui, les 404 d'à côté pourraient ne
    tenir qu'à un décor qui refuse tout le monde."""
    from conftest import ADMIN
    _ouvrir(db_path, deux_albums["c1"], "eva", niveau="ecriture")
    case = _case_dans(client, deux_albums["pl1"])
    perso = client.post("/api/personnages", json={"nom": "Narrateur"}, headers=ADMIN).json()["id"]
    h = {"Remote-User": "eva"}
    refus = client.put(f"/api/regions/{case}/locuteur", json={"personnage_id": perso}, headers=h)
    assert refus.status_code == 422 and "« case »" in refus.json()["detail"]
    assert _traces_de_locuteur(db_path) == (0, 0)
    pose = client.put(f"/api/regions/{deux_albums['r1']['id']}/locuteur",
                      json={"personnage_id": perso}, headers=h)
    assert pose.status_code == 200 and pose.json()["locuteur"]["id"] == perso
    assert _traces_de_locuteur(db_path) == (1, 1)


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

    # La même note posée dans les TROIS albums ; bob lit c1 et c3, pas c2. (Le tag et son
    # nuage qui tenaient ce rôle sont partis avec le basculement d'ANN-7.)
    for rid in (deux_albums["r1"]["id"], deux_albums["r2"]["id"], r3["id"]):
        client.put(f"/api/regions/{rid}/annotation", json={"note": "partout"}, headers=ADMIN)
    _ouvrir(db_path, deux_albums["c1"], "bob")
    _ouvrir(db_path, c3, "bob")
    h = {"Remote-User": "bob"}

    c = client.get("/api/corpus", headers=h).json()
    assert c["albums"] == 2 and c["planches"] == 2
    assert c["annotees"] == 2            # c1 + c3, jamais c2


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
    _case_export(db_path, deux_albums["c1"], "bob")   # DROIT-2 : sinon, le 403 de la porte
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
    _case_export(db_path, deux_albums["c1"], "bob")   # DROIT-2 : sinon, le 403 de la porte
    r = client.get("/api/analyse/accord-inter.csv", headers={"Remote-User": "bob"})
    assert r.status_code == 200, r.text
    assert "ICI" in r.text, "bob doit voir la divergence de SA collection"
    assert "AILLEURS" not in r.text, (
        "l'export inter cite une divergence d'une collection que bob n'écrit pas")
