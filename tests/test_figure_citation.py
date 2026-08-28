"""DROIT-1 — la figure citable, et la frontière CITER / PUBLIER.

Le chantier ne restreint presque rien : il rend POSSIBLE l'usage savant d'un corpus qu'on
ne peut pas diffuser. `statut_diffusion` ne borde rien à l'intérieur de l'instance
(arbitrage du 2026-08-28 : l'annotation repose sur les images) ; il devient opposable au
seul endroit où la donnée SORT, et il y distingue deux gestes que rien ne rapproche —
publier un corpus, ou citer une case en l'accompagnant d'un discours.
"""
import io
import json
import sqlite3
import zipfile

import pytest

import figure as figure_citable
from conftest import ADMIN


@pytest.fixture
def album_cite(client, db_path, png_bytes):
    """Un album documenté, dans une collection au régime `restreint` : le cas où citer est
    nécessaire et publier ne l'est pas."""
    a = client.post("/api/albums", json={
        "titre": "Le Lotus bleu", "serie": "Tintin", "auteur": "Hergé",
        "editeur": "Casterman", "date_edition": "1936", "isbn": "978-2-203-00104-6",
    }, headers=ADMIN).json()
    pl = client.post(f"/api/albums/{a['id']}/import", headers=ADMIN,
                     files={"file": ("p.png", png_bytes, "image/png")}).json()
    case = client.post(f"/api/planches/{pl['id']}/regions", headers=ADMIN,
                       json={"type": "case", "x": 0, "y": 0, "w": 40, "h": 40}).json()
    conn = sqlite3.connect(db_path)
    try:
        cid = conn.execute(
            "SELECT collection_id FROM collection_album WHERE album_id = ?",
            (a["id"],)).fetchone()[0]
        conn.execute("UPDATE collection SET nom = ?, statut_diffusion = ?, "
                     "licence_defaut = ? WHERE id = ?",
                     ("Étude coloniale", "restreint", "CC-BY-4.0", cid))
        conn.commit()
    finally:
        conn.close()
    return {"album": a, "planche": pl, "case": case, "collection": cid}


# --------------------------------------------------------------------------- #
# Le cœur : composer la légende
# --------------------------------------------------------------------------- #
def test_legende_complete(client, db_path, album_cite):
    """Ce qui rend une citation défendable, c'est qu'elle soit COURTE, IDENTIFIÉE et
    ACCOMPAGNÉE. L'outil produit donc les trois d'un geste — sinon l'accompagnement se
    recrée à la main, et c'est à la main qu'il se perd."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        leg = figure_citable.legende(conn, album_cite["case"]["id"])
    finally:
        conn.close()
    assert leg["titre"] == "Tintin — Le Lotus bleu"
    assert leg["auteur"] == "Hergé" and leg["editeur"] == "Casterman"
    assert leg["annee"] == "1936"
    assert leg["citation"].startswith("pl.")          # repère dérivé, jamais stocké
    assert leg["collection"] == "Étude coloniale"
    assert leg["licence"] == "CC-BY-4.0"
    assert "courte citation" in leg["mention_citation"]


def test_l_ordre_des_mentions_ne_depend_pas_de_la_demande(client, db_path, album_cite):
    """Une légende est une RÉFÉRENCE : son ordre est bibliographique, pas celui dans lequel
    on a coché les cases. Sans cela, deux figures de la même communication porteraient des
    légendes de forme différente."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        a = figure_citable.legende(conn, album_cite["case"]["id"],
                                   ["annee", "titre", "editeur"])
        b = figure_citable.legende(conn, album_cite["case"]["id"],
                                   ["editeur", "titre", "annee"])
    finally:
        conn.close()
    assert list(a) == list(b) == ["titre", "editeur", "annee"]


def test_un_champ_vide_ne_produit_pas_de_blanc(client, db_path, png_bytes):
    """Une légende ne doit pas annoncer « ISBN : » suivi du vide. Un champ demandé mais
    non renseigné disparaît — SAUF la base légale, cf. le test suivant."""
    a = client.post("/api/albums", json={"titre": "Sans métadonnées"},
                    headers=ADMIN).json()
    pl = client.post(f"/api/albums/{a['id']}/import", headers=ADMIN,
                     files={"file": ("p.png", png_bytes, "image/png")}).json()
    r = client.post(f"/api/planches/{pl['id']}/regions", headers=ADMIN,
                    json={"type": "case", "x": 0, "y": 0, "w": 20, "h": 20}).json()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        leg = figure_citable.legende(conn, r["id"])
    finally:
        conn.close()
    assert "isbn" not in leg and "editeur" not in leg and "auteur" not in leg
    assert leg["titre"] == "Sans métadonnées"


def test_la_base_legale_absente_se_dit(client, db_path, album_cite):
    """Le seul champ qui parle même vide. « Non établie » est une INFORMATION, et c'est
    aujourd'hui la vérité du dépôt (DEPOT-1) : la taire ferait passer pour réglé ce qui ne
    l'est pas, sur l'artefact même qui sort de l'instance."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        leg = figure_citable.legende(conn, album_cite["case"]["id"])
    finally:
        conn.close()
    assert leg["base_legale"] == figure_citable.BASE_LEGALE_ABSENTE
    assert "non établie" in figure_citable.texte(leg)


def test_les_contributions_N0_priment_sur_l_auteur_legacy(client, db_path, album_cite):
    """`albums.auteur` est *legacy* ; `contribution` (v15) est le modèle Zotero-like. On ne
    mélange pas les deux : une légende qui répéterait le même nom sous deux formes se lit
    comme une erreur."""
    client.post(f"/api/albums/{album_cite['album']['id']}/contributions", headers=ADMIN,
                json={"nom": "Hergé", "role": "scénariste"})
    client.post(f"/api/albums/{album_cite['album']['id']}/contributions", headers=ADMIN,
                json={"nom": "Edgar P. Jacobs", "role": "coloriste"})
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        leg = figure_citable.legende(conn, album_cite["case"]["id"])
    finally:
        conn.close()
    assert leg["auteur"] == "Hergé (scénariste), Edgar P. Jacobs (coloriste)"


def test_texte_separe_la_reference_du_cadre(client, db_path, album_cite):
    """Un lecteur doit distinguer d'un coup d'œil ce qui décrit l'ŒUVRE citée de ce qui
    décrit les CONDITIONS de sa reproduction."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rendu = figure_citable.texte(
            figure_citable.legende(conn, album_cite["case"]["id"]))
    finally:
        conn.close()
    assert rendu.startswith("Tintin — Le Lotus bleu, Hergé, Casterman, 1936")
    assert "Corpus : Étude coloniale" in rendu
    assert "Licence du jeu enrichi : CC-BY-4.0" in rendu


# --------------------------------------------------------------------------- #
# La route : le zip qui sort
# --------------------------------------------------------------------------- #
def test_export_figure_produit_image_legende_et_notice(client, album_cite):
    """Le paquet lie l'image à sa référence. C'est tout l'objet : une image nue se
    recrédite à la main, et c'est à la main que le crédit se perd."""
    r = client.post("/api/figures", headers=ADMIN,
                    json={"regions": [album_cite["case"]["id"]]})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    noms = sorted(zf.namelist())
    assert len(noms) == 3
    base = noms[0].rsplit(".", 1)[0]
    assert sorted(n.rsplit(".", 1)[1] for n in noms) == ["json", "png", "txt"]
    assert zf.read(f"{base}.png")[:8] == b"\x89PNG\r\n\x1a\n"
    notice = json.loads(zf.read(f"{base}.json"))
    assert notice["region_id"] == album_cite["case"]["id"]
    assert notice["titre"] == "Tintin — Le Lotus bleu"
    assert "courte citation" in zf.read(f"{base}.txt").decode("utf-8")


def test_le_nom_de_fichier_porte_le_repere(client, album_cite):
    """Une figure se retrouve dans un dossier de travail par ce qu'elle MONTRE, pas par sa
    clé primaire. Le nom dérive donc de la citation (« pl. 1 · c1 » → « pl-1-c1 »).

    Le repli sur l'id n'est PAS un cas dégradé : il se produit dès qu'on ne demande pas la
    mention `citation`, et un fichier doit rester nommé quoi qu'on ait coché.
    """
    r = client.post("/api/figures", headers=ADMIN,
                    json={"regions": [album_cite["case"]["id"]]})
    noms = {n.rsplit(".", 1)[0] for n in
            zipfile.ZipFile(io.BytesIO(r.content)).namelist()}
    assert noms == {"pl-1-c1"}
    sans = client.post("/api/figures", headers=ADMIN, json={
        "regions": [album_cite["case"]["id"]], "champs": ["titre"]})
    noms = {n.rsplit(".", 1)[0] for n in
            zipfile.ZipFile(io.BytesIO(sans.content)).namelist()}
    assert noms == {f"region-{album_cite['case']['id']}"}


def test_les_mentions_sont_choisies(client, album_cite):
    """Arbitrage du chantier : la personne qui cite choisit ce qui apparaît. Une légende
    d'article, une légende de diapositive et une notice de catalogue n'ont pas les mêmes
    besoins, et imposer un gabarit obligerait à le retailler hors de l'outil."""
    r = client.post("/api/figures", headers=ADMIN, json={
        "regions": [album_cite["case"]["id"]], "champs": ["titre", "citation"]})
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    base = zf.namelist()[0].rsplit(".", 1)[0]
    notice = json.loads(zf.read(f"{base}.json"))
    assert set(notice) == {"region_id", "titre", "citation"}
    assert "Casterman" not in zf.read(f"{base}.txt").decode("utf-8")


def test_une_mention_inconnue_est_refusee(client, album_cite):
    """Le jeu de mentions est fermé : une faute de frappe doit se voir, pas produire
    silencieusement une légende amputée."""
    r = client.post("/api/figures", headers=ADMIN, json={
        "regions": [album_cite["case"]["id"]], "champs": ["titre", "coypright"]})
    assert r.status_code == 422 and "coypright" in r.json()["detail"]


def test_un_lot_de_figures(client, album_cite):
    """Une communication a besoin de plusieurs figures. Le lot est un confort, PAS une
    frontière : la ligne entre citer et publier passe par la nature de l'acte, pas par un
    volume — un plafond serait un chiffre qu'on ne sait pas justifier."""
    autre = client.post(f"/api/planches/{album_cite['planche']['id']}/regions",
                        headers=ADMIN,
                        json={"type": "case", "x": 40, "y": 0, "w": 40, "h": 40}).json()
    r = client.post("/api/figures", headers=ADMIN,
                    json={"regions": [album_cite["case"]["id"], autre["id"]]})
    assert len({n.rsplit(".", 1)[0] for n in
                zipfile.ZipFile(io.BytesIO(r.content)).namelist()}) == 2


def test_citer_ne_contourne_pas_le_cloisonnement(client, db_path, album_cite,
                                                 derriere_proxy):
    """Citer s'AJOUTE au cloisonnement d'AUTH-2, il ne s'y substitue pas : on ne cite que
    ce qu'on voit. Sans cette garde, la figure serait devenue le trou par lequel tout le
    corpus se lit en images."""
    r = client.post("/api/figures", headers={"Remote-User": "etranger"},
                    json={"regions": [album_cite["case"]["id"]]})
    assert r.status_code == 404


def test_le_regime_restreint_ne_bloque_pas_la_citation(client, album_cite):
    """LA décision du chantier. Citer relève du droit de citation, pas de la diffusion, et
    un fonds sous droits est justement celui qu'on cite plutôt que de le diffuser. La
    collection est `restreint` : la figure sort quand même — accompagnée."""
    r = client.post("/api/figures", headers=ADMIN,
                    json={"regions": [album_cite["case"]["id"]]})
    assert r.status_code == 200


def test_les_champs_offerts_sont_publies(client):
    """L'UI ne devine pas les mentions disponibles : elle les demande. La route décrit un
    FORMAT et non un corpus — d'où son absence de portée, écrite dans le cliquet."""
    champs = client.get("/api/figure/champs").json()
    assert [c["champ"] for c in champs] == list(figure_citable.CHAMPS)
    assert all(c["libelle"] for c in champs)


def test_la_collection_creditee_est_une_qu_on_LIT(client, db_path, album_cite,
                                                  derriere_proxy):
    """Trouvé en relisant, sur une suite verte.

    Un album vit dans PLUSIEURS collections depuis AUTH-3. Sans filtre, la légende
    créditait la plus ancienne — y compris une étude qu'on n'a pas le droit de voir, dont
    elle exportait alors le NOM, la licence et la base légale. Et pas seulement à l'écran :
    dans un artefact qui quitte l'instance.

    C'est la même fuite « par la bande » qu'AUTH-2 avait trouvée sur les attributs d'un
    objet partagé, revenue par la porte du chantier suivant.
    """
    import sqlite3
    from conftest import ADMIN
    # Une SECONDE collection, plus ancienne (id plus petit) et invisible à bob.
    conn = sqlite3.connect(db_path)
    try:
        secrete = conn.execute(
            "INSERT INTO collection (nom, licence_defaut) VALUES ('Étude secrète', 'X')"
        ).lastrowid
        # …placée AVANT celle de l'album dans l'ordre d'id : on force le cas défavorable.
        conn.execute("UPDATE collection SET id = ? WHERE id = ?",
                     (999, album_cite["collection"]))
        conn.execute("UPDATE collection_album SET collection_id = ? WHERE album_id = ?",
                     (999, album_cite["album"]["id"]))
        conn.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                     (secrete, album_cite["album"]["id"]))
        conn.execute("INSERT INTO collection_acces (collection_id, genre, principal, "
                     "niveau) VALUES (?, 'utilisateur', 'bob', 'lecture')", (999,))
        conn.commit()
    finally:
        conn.close()
    r = client.post("/api/figures", headers={"Remote-User": "bob"},
                    json={"regions": [album_cite["case"]["id"]]})
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    base = zf.namelist()[0].rsplit(".", 1)[0]
    notice = json.loads(zf.read(f"{base}.json"))
    assert notice["collection"] == "Étude coloniale"      # celle qu'il LIT
    assert "secrète" not in zf.read(f"{base}.txt").decode("utf-8")
