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
import pytest
from fastapi.routing import APIRoute
from starlette.routing import Mount

import autorisation
import main


# --------------------------------------------------------------------------- #
# Ce qui ne consulte pas la portée, et pourquoi
# --------------------------------------------------------------------------- #
# Une route est ici parce qu'on a décidé qu'elle y soit, avec la raison écrite à côté.
# Ajouter une ligne ici est un ACTE : c'est déclarer qu'une route peut toucher au serveur
# sans demander qui appelle.
HORS_PERIMETRE = {
    ("GET", "/"): "coquille HTML, aucune donnée — le contenu vient des routes /api",
    ("GET", "/recherche"): "idem",
    ("GET", "/corpus"): "idem",
    ("GET", "/exploration"): "idem",
    ("GET", "/api/sante"): (
        "état des moteurs ML, aucune donnée de corpus. Doit rester joignable sans "
        "identité : c'est la sonde d'un conteneur, appelée avant qu'Authelia ne soit "
        "forcément debout"),
    ("GET", "/api/moi"): (
        "renvoie l'identité de l'APPELANT et rien d'autre. C'est la brique sur laquelle "
        "la portée se calcule ; l'y soumettre serait circulaire"),
    ("GET", "/api/sauvegarde"): (
        "DÉCISION DU 2026-08-27, assumée : la sauvegarde reste ouverte à tous. Elle "
        "déverse la base ENTIÈRE, donc toute personne ayant accès à l'instance peut "
        "aspirer l'intégralité du corpus. Le cloisonnement du reste protège de "
        "l'accident et de la confusion, pas d'une exfiltration délibérée. "
        "Cf. docs/hebergement-securite.md et pilotage/AUTH-2.md"),
    ("POST", "/api/sharedocs/deposer-sauvegarde"): (
        "même sauvegarde, poussée sur WebDAV — même décision"),
    ("GET", "/api/sharedocs/etat"): "état de la session WebDAV distante, pas le corpus",
    ("POST", "/api/sharedocs/connexion"): "idem (session par personne : cf. SHARE-1)",
    ("POST", "/api/sharedocs/deconnexion"): "idem",
    ("GET", "/api/sharedocs/liste"): "liste un dossier DISTANT, pas la base locale",
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
    ("POST", "/api/sharedocs/importer"),
    ("GET", "/api/tags"),
    ("POST", "/api/tags"),
    ("GET", "/api/contribution-roles"),
    ("POST", "/api/contribution-roles"),
    ("GET", "/api/albums/{album_id}/contributions"),
    ("POST", "/api/albums/{album_id}/contributions"),
    ("DELETE", "/api/contributions/{contribution_id}"),
    ("GET", "/api/personnages"),
    ("POST", "/api/personnages"),
    ("PUT", "/api/personnages/{personnage_id}"),
    ("DELETE", "/api/personnages/{personnage_id}"),
    ("POST", "/api/personnages/{personnage_id}/fusion"),
    ("GET", "/api/personnages/{personnage_id}/alignements"),
    ("POST", "/api/personnages/{personnage_id}/alignements"),
    ("DELETE", "/api/personnages/{personnage_id}/alignements/{alignement_id}"),
    ("GET", "/api/undo/prochain"),
    ("POST", "/api/undo"),
    ("GET", "/api/domaines"),
    ("POST", "/api/domaines"),
    ("PATCH", "/api/domaines/{dom_id}"),
    ("DELETE", "/api/domaines/{dom_id}"),
    ("PATCH", "/api/domaines/{dom_id}/lexique"),
    ("GET", "/api/attributs/dimensions"),
    ("POST", "/api/attributs/dimensions"),
    ("PATCH", "/api/attributs/dimensions/{dim_id}/domaine"),
    ("DELETE", "/api/attributs/dimensions/{dim_id}"),
    ("GET", "/api/attributs/dimensions/{dim_id}/valeurs"),
    ("POST", "/api/attributs/dimensions/{dim_id}/valeurs"),
    ("DELETE", "/api/attributs/valeurs/{val_id}"),
    ("GET", "/api/attributs/valeurs"),
    ("PUT", "/api/attributs/valeurs/{val_id}"),
    ("POST", "/api/attributs/valeurs/{val_id}/fusion"),
    ("GET", "/api/collections"),
    ("GET", "/api/lexique"),
    ("POST", "/api/lexique/importer"),
    ("PATCH", "/api/attributs/dimensions/{dim_id}/lexique"),
    ("PATCH", "/api/attributs/valeurs/{val_id}/lexique"),
    ("PATCH", "/api/tags/{tag_id}/lexique"),
    ("GET", "/api/personnages/{personnage_id}/attributs"),
    ("PUT", "/api/personnages/{personnage_id}/attributs"),
    ("DELETE", "/api/personnages/{personnage_id}/attributs/{valeur_id}"),
    ("GET", "/api/analyse/accord"),
    ("GET", "/api/analyse/accord-inter"),
    ("PUT", "/api/regions/{region_id}/tokens/{ordre}"),
    ("POST", "/api/regions/{region_id}/grammaire/valider"),
    ("DELETE", "/api/regions/{region_id}/tokens/{ordre}"),
    ("GET", "/api/analyse/info"),
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


def _dependances(dependant, vues=None) -> set:
    """Toutes les fonctions de dépendance atteignables depuis une route (transitif)."""
    vues = set() if vues is None else vues
    for d in dependant.dependencies:
        if d.call is not None:
            vues.add(d.call)
        _dependances(d, vues)
    return vues


def _routes() -> list[tuple[str, str, bool]]:
    """(méthode, chemin, consulte-t-elle la portée ?) pour chaque route de l'app."""
    out = []
    for r in main.app.routes:
        if not isinstance(r, APIRoute):
            continue
        deps = _dependances(r.dependant)
        scopee = main.portee_courante in deps
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


def test_aucun_montage_ne_sert_le_corpus():
    """Un montage de fichiers statiques ne passe par AUCUNE dépendance : le cliquet des
    routes ne peut pas le voir. Il lui faut donc sa propre porte."""
    inconnus = [r.path for r in main.app.routes
                if isinstance(r, Mount) and r.path not in MONTAGES_AUTORISES]
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
    _ouvrir(db_path, deux_albums["c1"], "bob")
    c = client.get("/api/corpus", headers={"Remote-User": "bob"}).json()
    assert c["albums"] == 1 and c["planches"] == 1


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
