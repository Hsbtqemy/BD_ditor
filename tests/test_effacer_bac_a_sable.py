"""COL-4 — effacer un bac à sable : la remise à neuf, l'effacement hebdomadaire, l'outil.

Le décor de la relecture croisée (cadrage) : une base qui porte le jeu, trois bacs à sable
dont un expiré, une copie gardée au fonds dans l'un, un document importé dans un autre — et
un vrai projet à côté, qui ne doit rien perdre.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

import autorisation
import database
import socle
from conftest import ADMIN, make_png
from test_bac_a_sable import DOC_GRAMMAIRE, HUGO, LEA, RESP, SAM, _copie, _sql
from test_jeu import DOC_EXEMPLE, DOC_PARCOURS, DOC_STOCK_SERVEUR, ecrire_jeu

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import effacer_bacs_a_sable  # noqa: E402
import preparer_jeu  # noqa: E402


@pytest.fixture
def jeu(client, tmp_path):
    depot = ecrire_jeu(tmp_path / "jeu-depot", [DOC_PARCOURS, DOC_EXEMPLE, DOC_GRAMMAIRE],
                       images=("p1.png", "p2.png", "p3.png"))
    serveur = ecrire_jeu(tmp_path / "jeu-serveur", [DOC_STOCK_SERVEUR], images=("s1.png",))
    conn = database.get_connection()
    try:
        preparer_jeu.preparer(conn, depot=depot, serveur=serveur, appliquer_=True,
                              dire=lambda _l: None)
    finally:
        conn.close()
    return {"depot": depot, "serveur": serveur}


@pytest.fixture
def decor(client, db_path, jeu, derriere_proxy):
    for qui in (LEA, SAM, RESP, HUGO):
        client.get("/api/moi", headers=qui)
    etude = client.post("/api/projets", json={"nom": "Étude"}, headers=ADMIN).json()["id"]
    client.put(f"/api/projets/{etude}/membres", headers=ADMIN,
               json={"genre": "utilisateur", "principal": "resp", "role": "responsable"})
    col = client.post("/api/collections", headers=RESP,
                      json={"nom": "Corpus", "projet_id": etude}).json()["id"]
    reel = client.post("/api/albums", headers=RESP,
                       json={"titre": "Réel", "collection_id": col}).json()["id"]
    client.post(f"/api/albums/{reel}/import", headers=RESP,
                files={"file": ("p.png", make_png(), "image/png")})
    bac = client.post("/api/bac-a-sable", headers=LEA).json()
    client.put(f"/api/projets/{bac['id']}/membres", headers=LEA,
               json={"genre": "utilisateur", "principal": "sam", "role": "membre"})
    # Un document importé dans le bac à sable de lea, avec une planche.
    importe = client.post("/api/albums", headers=LEA,
                          json={"titre": "Importé", "collection_id": bac["base"]["id"]}
                          ).json()["id"]
    client.post(f"/api/albums/{importe}/import", headers=LEA,
                files={"file": ("p.png", make_png(300, 300, "red"), "image/png")})
    # Du travail de l'invité sur une copie du jeu, un tag né local, une collection à lui.
    planche = _copie({"bac": bac, "db": db_path}, "exemple")["planche_ids"][0]
    region = client.post(f"/api/planches/{planche}/regions", headers=SAM,
                         json={"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9}).json()["id"]
    client.put(f"/api/regions/{region}/annotation", headers=SAM,
               json={"note": "essai", "tags": ["mot-de-sam"]})
    client.post("/api/collections", headers=SAM,
                json={"nom": "Chez Sam", "projet_id": bac["id"]})
    # Le bac à sable de resp, avec une copie GARDÉE au fonds ; celui de hugo, expiré. Rien
    # ne part plus au fonds depuis un bac à sable (la route le refuse) : la copie gardée est
    # posée en base, l'état que l'effacement doit encore savoir prendre (une base d'avant
    # ce refus, ou retouchée).
    bac_resp = client.post("/api/bac-a-sable", headers=RESP).json()
    gardee = bac_resp["jeu"][0]["album_id"]
    assert client.delete(f"/api/albums/{gardee}/collections/{bac_resp['base']['id']}",
                         headers=RESP).status_code == 409
    _sql(db_path, "UPDATE albums SET projet_id = ? WHERE id = ?", (bac_resp["id"], gardee))
    _sql(db_path, "DELETE FROM collection_album WHERE album_id = ?", (gardee,))
    bac_hugo = client.post("/api/bac-a-sable", headers=HUGO).json()
    _sql(db_path, "UPDATE projet SET efface_le = '2000-01-01 00:00:00' WHERE id = ?",
         (bac_hugo["id"],))
    return {"db": db_path, "data": db_path.parent, "etude": etude, "col": col, "reel": reel,
            "bac": bac, "importe": importe, "region_sam": region, "bac_resp": bac_resp,
            "gardee": gardee, "bac_hugo": bac_hugo}


def _etat_du_reel(db):
    """Ce que le vrai projet et la référence du jeu possèdent : rien n'en doit partir."""
    return {
        "albums": _sql(db, "SELECT a.id, a.titre FROM albums a WHERE a.projet_id NOT IN "
                           "(SELECT id FROM projet WHERE bac_a_sable_de IS NOT NULL) "
                           "ORDER BY a.id"),
        "planches": _sql(db, "SELECT p.id, p.chemin_tiff FROM planches p JOIN albums a "
                             "ON a.id = p.album_id WHERE a.projet_id NOT IN "
                             "(SELECT id FROM projet WHERE bac_a_sable_de IS NOT NULL) "
                             "ORDER BY p.id"),
        "projets": _sql(db, "SELECT id, nom FROM projet WHERE bac_a_sable_de IS NULL "
                            "ORDER BY id"),
        "collections": _sql(db, "SELECT c.id FROM collection c JOIN projet p ON p.id = "
                                "COALESCE(c.projet_id, (SELECT id FROM projet WHERE repli = 1)) "
                                "WHERE p.bac_a_sable_de IS NULL ORDER BY c.id"),
        "jeu": _sql(db, "SELECT * FROM jeu_document ORDER BY document_id"),
    }


def _effacer(projet_id, portee=autorisation.TOTALE, motif="effacement"):
    conn = database.get_connection()
    try:
        return socle._effacer_bac_a_sable(conn, portee, projet_id, motif=motif)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Le chemin de l'effacement
# --------------------------------------------------------------------------- #
def test_effacer_un_bac_a_sable_emporte_tout_ce_qu_il_porte(client, decor):
    db, pid = decor["db"], decor["bac"]["id"]
    avant = _etat_du_reel(db)
    images_importees = [r["chemin_tiff"] for r in _sql(
        db, "SELECT chemin_tiff FROM planches WHERE album_id = ?", (decor["importe"],))]
    r = _effacer(pid)
    assert r["efface"] and r["albums"] == 5
    assert _sql(db, "SELECT id FROM projet WHERE id = ?", (pid,)) == []
    assert _sql(db, "SELECT COUNT(*) AS n FROM projet_acces WHERE projet_id = ?",
                (pid,)) == [{"n": 0}]
    assert _sql(db, f"SELECT id FROM collection WHERE projet_id = ?", (pid,)) == []
    # Le tag né local part avec lui ; il ne devient pas global.
    assert _sql(db, "SELECT id FROM tags WHERE label = 'mot-de-sam'") == []
    # Le document importé part avec sa dernière copie, et ses images.
    assert _sql(db, "SELECT id FROM albums WHERE id = ?", (decor["importe"],)) == []
    assert images_importees and not any((decor["data"] / c).exists()
                                        for c in images_importees)
    # Le reste — vrai projet, jeu, autres bacs à sable — est intact.
    assert _etat_du_reel(db) == avant
    assert _sql(db, "SELECT COUNT(*) AS n FROM projet WHERE bac_a_sable_de IS NOT NULL"
                ) == [{"n": 2}]
    # L'acte s'écrit.
    assert _sql(db, "SELECT json_extract(avant, '$.motif') AS motif, "
                    "json_extract(avant, '$.bac_a_sable') AS bac FROM evenement "
                    "WHERE cible_table = 'projet' AND type = 'suppression' AND cible_id = ?",
                (pid,)) == [{"motif": "effacement", "bac": 1}]


def test_les_images_du_jeu_restent(client, decor):
    """Le mutant écrit dans le cadrage : effacer les dossiers d'une copie sans lire les
    références. Après l'effacement de TOUS les bacs à sable, chaque fichier de la référence
    est toujours là."""
    db = decor["db"]
    refs = [r["chemin_tiff"] for r in _sql(db, "SELECT p.chemin_tiff FROM planches p JOIN "
                                               "jeu_document jd ON jd.album_reference = "
                                               "p.album_id")]
    for pid in (decor["bac"]["id"], decor["bac_resp"]["id"], decor["bac_hugo"]["id"]):
        _effacer(pid)
    assert refs and all((decor["data"] / c).is_file() for c in refs)
    assert _sql(db, "SELECT COUNT(*) AS n FROM jeu_document") == [{"n": 4}]


def test_une_copie_gardee_au_fonds_part_avec_son_bac_a_sable(client, decor):
    db = decor["db"]
    assert _sql(db, "SELECT id FROM albums WHERE id = ?", (decor["gardee"],))
    _effacer(decor["bac_resp"]["id"])
    assert _sql(db, "SELECT id FROM albums WHERE id = ?", (decor["gardee"],)) == []


@pytest.mark.parametrize("quel", ["repli", "etude", "jeu"])
def test_jamais_un_projet_ordinaire_le_repli_ou_le_jeu(client, decor, quel):
    db = decor["db"]
    pid = {"repli": _sql(db, "SELECT id FROM projet WHERE repli = 1")[0]["id"],
           "etude": decor["etude"],
           "jeu": _sql(db, "SELECT id FROM projet WHERE jeu = 1")[0]["id"]}[quel]
    avant = _etat_du_reel(db)
    with pytest.raises(Exception) as exc:
        _effacer(pid)
    assert getattr(exc.value, "status_code", None) == 409
    assert _etat_du_reel(db) == avant


def test_l_effacement_est_idempotent(client, decor):
    pid = decor["bac"]["id"]
    assert _effacer(pid)["efface"] is True
    assert _effacer(pid) == {"efface": False, "albums": 0, "gestes_passes": 0}


def test_un_effacement_interrompu_se_finit(client, decor, monkeypatch):
    """`_detruire_album` commite album par album : un arrêt au milieu laisse un bac à sable à
    moitié effacé, que l'appel suivant finit."""
    pid = decor["bac"]["id"]
    vrai = socle._detruire_album
    appels = []

    def casse(conn, portee, album_id, **k):
        appels.append(album_id)
        if len(appels) == 2:
            raise RuntimeError("arrêt brutal")
        return vrai(conn, portee, album_id, **k)

    monkeypatch.setattr(socle, "_detruire_album", casse)
    with pytest.raises(RuntimeError):
        _effacer(pid)
    monkeypatch.setattr(socle, "_detruire_album", vrai)
    assert _sql(decor["db"], "SELECT id FROM projet WHERE id = ?", (pid,))
    assert _effacer(pid)["efface"] is True


def test_un_album_ne_pendant_l_effacement_part_avec_le_bac(client, decor, monkeypatch):
    """Un invité crée un album dans la base pendant que l'effacement détruit les autres
    (relecture croisée : la liste des albums lue une fois, la suppression du projet tombait
    sur une clé étrangère — 500, un bac à sable à moitié effacé). Les albums se relisent
    sous le verrou : celui-là part aussi, et le bac à sable avec."""
    vrai = socle._detruire_album
    fait = {}

    def pendant(conn, portee, album_id, **kw):
        vrai(conn, portee, album_id, **kw)
        if not fait:
            r = client.post("/api/albums", headers=SAM,
                            json={"titre": "Né pendant",
                                  "collection_id": decor["bac"]["base"]["id"]})
            assert r.status_code == 201, r.text
            fait["id"] = r.json()["id"]

    monkeypatch.setattr(socle, "_detruire_album", pendant)
    r = client.post("/api/bac-a-sable/remise-a-neuf", headers=LEA)
    assert r.status_code == 200, r.text
    assert _sql(decor["db"], "SELECT id FROM albums WHERE id = ?", (fait["id"],)) == []
    assert _sql(decor["db"], "SELECT id FROM projet WHERE id = ?", (decor["bac"]["id"],)) == []
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM projet WHERE bac_a_sable_de = 'lea'"
                ) == [{"n": 1}]


def test_un_effacement_qui_ne_finit_pas_se_refuse_proprement(client, decor, monkeypatch):
    """Si des albums naissent à chaque tour, l'effacement renonce après ses tours par un
    409 qui dit de réessayer — jamais un 500."""
    monkeypatch.setattr(socle, "_TOURS_D_EFFACEMENT", 2)
    vrai = socle._detruire_album

    def toujours(conn, portee, album_id, **kw):
        vrai(conn, portee, album_id, **kw)
        client.post("/api/albums", headers=SAM,
                    json={"titre": "Encore", "collection_id": decor["bac"]["base"]["id"]})

    monkeypatch.setattr(socle, "_detruire_album", toujours)
    with pytest.raises(socle.HTTPException) as e:
        _effacer(decor["bac"]["id"])
    assert e.value.status_code == 409 and "réessayez" in e.value.detail
    monkeypatch.setattr(socle, "_detruire_album", vrai)
    assert _effacer(decor["bac"]["id"])["efface"] is True


def test_un_seul_bac_a_sable_par_login(client, decor, monkeypatch):
    """La remise à neuf relit SOUS le verrou : un clic sur « Mon bac à sable » arrivé entre
    l'effacement et la création ne fait pas naître un second bac à sable (relecture
    croisée). Et la base le garantit (index unique partiel)."""
    import routes.bac_a_sable as module
    vrai = socle._effacer_bac_a_sable

    def puis_un_clic(conn, portee, pid, *, motif):
        res = vrai(conn, portee, pid, motif=motif)
        autre = database.get_connection()
        try:
            import conflit
            conflit.verrouiller(autre)
            socle._creer_bac_a_sable(autre, "lea")
            autre.commit()
        finally:
            autre.close()
        return res

    monkeypatch.setattr(module, "_effacer_bac_a_sable", puis_un_clic)
    tentes = []
    vrai_creer = module._creer_bac_a_sable
    monkeypatch.setattr(module, "_creer_bac_a_sable",
                        lambda conn, login: tentes.append(login) or vrai_creer(conn, login))
    r = client.post("/api/bac-a-sable/remise-a-neuf", headers=LEA)
    assert r.status_code == 200, r.text
    assert tentes == [], "la remise à neuf n'a pas relu sous le verrou"
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM projet WHERE bac_a_sable_de = 'lea'"
                ) == [{"n": 1}]
    c = sqlite3.connect(decor["db"])
    try:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("INSERT INTO projet (nom, bac_a_sable_de) VALUES ('Bac à sable', 'lea')")
        c.execute("INSERT INTO projet (nom) VALUES ('Ordinaire 1')")
        c.execute("INSERT INTO projet (nom) VALUES ('Ordinaire 2')")
        c.rollback()
    finally:
        c.close()


def test_l_index_rend_le_bac_qui_existe(client, decor, monkeypatch):
    """Le dernier mot de l'index : un chemin qui aurait créé son bac à sable sans le verrou
    (simulé : la relecture sous le verrou ne le voit pas) — `POST /api/bac-a-sable` rend
    celui qui existe, sans 500."""
    import routes.bac_a_sable as module
    vrai = module._mien
    appels = []

    def aveugle(conn, login):
        appels.append(login)
        return None if len(appels) <= 1 else vrai(conn, login)

    monkeypatch.setattr(module, "_mien", aveugle)
    r = client.post("/api/bac-a-sable", headers=LEA)
    assert r.status_code == 200 and r.json()["id"] == decor["bac"]["id"], r.text


def test_ctrl_z_ne_bute_pas_sur_un_bac_a_sable_efface(client, decor):
    """Le témoin de l'annulation : les gestes de sam dans le bac à sable sont PASSÉS à
    l'effacement ; son prochain Ctrl+Z ne refuse pas l'un après l'autre des gestes dont les
    objets ont disparu."""
    # Un geste de sam HORS du bac à sable, plus ancien : c'est lui que Ctrl+Z doit trouver.
    _sql(decor["db"], "INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
                      "VALUES (?, 'utilisateur', 'sam', 'ecriture')", (decor["col"],))
    planche = _sql(decor["db"], "SELECT id FROM planches WHERE album_id = ?",
                   (decor["reel"],))[0]["id"]
    hors = client.post(f"/api/planches/{planche}/regions", headers=SAM,
                       json={"type": "case", "x": 0, "y": 0, "w": 9, "h": 9}).json()["id"]
    planche_bac = _copie({"bac": decor["bac"], "db": decor["db"]}, "exemple")["planche_ids"][0]
    client.post(f"/api/planches/{planche_bac}/regions", headers=SAM,
                json={"type": "case", "x": 1, "y": 1, "w": 9, "h": 9})
    r = _effacer(decor["bac"]["id"])
    assert r["gestes_passes"] >= 3
    prochain = client.get("/api/undo/prochain", headers=SAM).json()
    attendu = _sql(decor["db"], "SELECT id FROM evenement WHERE cible_table = 'regions' "
                                "AND type = 'creation' AND cible_id = ?", (hors,))[0]["id"]
    assert prochain and prochain["evenement_id"] == attendu, prochain


# --------------------------------------------------------------------------- #
# La remise à neuf
# --------------------------------------------------------------------------- #
def test_la_remise_a_neuf(client, decor):
    db, ancien = decor["db"], decor["bac"]["id"]
    r = client.post("/api/bac-a-sable/remise-a-neuf", headers=LEA)
    assert r.status_code == 200, r.text
    neuf = r.json()
    assert neuf["id"] != ancien and len(neuf["jeu"]) == 4
    assert _sql(db, "SELECT id FROM projet WHERE id = ?", (ancien,)) == []
    assert neuf["planches_importees"] == 0
    # L'invité n'y est plus : un bac à sable neuf naît sans invité.
    assert _sql(db, "SELECT principal FROM projet_acces WHERE projet_id = ?",
                (neuf["id"],)) == [{"principal": "lea"}]
    assert _sql(db, "SELECT json_extract(avant, '$.motif') AS m FROM evenement "
                    "WHERE cible_table = 'projet' AND type = 'suppression' "
                    "AND cible_id = ?", (ancien,)) == [{"m": "remise à neuf"}]


def test_la_remise_a_neuf_est_au_proprietaire(client, decor):
    """L'invité ne remet pas à neuf le bac à sable d'un autre : il n'a pas le sien (404) ;
    l'administrateur remet à neuf le sien, pas celui de lea."""
    assert client.post("/api/bac-a-sable/remise-a-neuf", headers=SAM).status_code == 404
    r = client.post("/api/bac-a-sable/remise-a-neuf", headers=HUGO)
    assert r.status_code == 200 and r.json()["id"] != decor["bac_hugo"]["id"]
    assert _sql(decor["db"], "SELECT id FROM projet WHERE id = ?", (decor["bac"]["id"],))
    assert client.post("/api/bac-a-sable/remise-a-neuf").status_code == 403


# --------------------------------------------------------------------------- #
# L'outil
# --------------------------------------------------------------------------- #
def _outil(**k):
    conn = database.get_connection()
    try:
        return effacer_bacs_a_sable.effacer(conn, dire=lambda _l: None, **k)
    finally:
        conn.close()


def test_l_outil_n_efface_que_les_bacs_a_sable_echus(client, decor):
    db = decor["db"]
    assert _outil()["a_effacer"] == [decor["bac_hugo"]["id"]]
    assert _sql(db, "SELECT id FROM projet WHERE id = ?", (decor["bac_hugo"]["id"],))
    bilan = _outil(appliquer=True)
    assert bilan["effaces"] == [decor["bac_hugo"]["id"]]
    assert _sql(db, "SELECT COUNT(*) AS n FROM projet WHERE bac_a_sable_de IS NOT NULL"
                ) == [{"n": 2}]
    # Au moment venu, tous partent — sans exception.
    lundi = _sql(db, "SELECT MAX(efface_le) AS m FROM projet")[0]["m"]
    assert sorted(_outil(maintenant=lundi, appliquer=True)["effaces"]) == sorted(
        [decor["bac"]["id"], decor["bac_resp"]["id"]])
    assert _sql(db, "SELECT COUNT(*) AS n FROM projet WHERE bac_a_sable_de IS NOT NULL"
                ) == [{"n": 0}]


def test_l_outil_purge_une_reference_que_plus_rien_ne_tient(client, decor):
    """Un document retiré du jeu reste tant qu'un bac à sable en tient une copie ; le
    dernier effacé, la référence part."""
    ecrire_jeu(decor["data"] / "jeu-vide", [], images=())
    conn = database.get_connection()
    try:
        bilan = preparer_jeu.preparer(conn, depot=decor["data"] / "jeu-vide",
                                      serveur=None, appliquer_=True, dire=lambda _l: None)
    finally:
        conn.close()
    assert bilan["purges"] == []                     # trois bacs à sable les tiennent
    assert _outil(tous=True, appliquer=True)["references"]
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM albums a JOIN projet p ON p.id = "
                             "a.projet_id WHERE p.jeu = 1") == [{"n": 1}]   # le serveur


def test_l_outil_a_blanc_n_ecrit_rien_et_la_ligne_de_commande(client, decor, monkeypatch,
                                                              capsys):
    monkeypatch.setattr(database, "DB_PATH", decor["db"])
    assert effacer_bacs_a_sable.main([]) == 0
    assert "À blanc : 1" in capsys.readouterr().out
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM projet WHERE bac_a_sable_de IS NOT NULL"
                ) == [{"n": 3}]
    assert effacer_bacs_a_sable.main(["--appliquer"]) == 0
    assert _sql(decor["db"], "SELECT COUNT(*) AS n FROM projet WHERE bac_a_sable_de IS NOT NULL"
                ) == [{"n": 2}]


def test_l_outil_isole_chaque_bac_a_sable(client, decor, monkeypatch, capsys):
    """Une erreur sur un bac à sable n'arrête plus le battement (relecture croisée) : elle
    est défaite, dite sur la sortie, comptée ; les autres s'effacent ; le code de retour
    dit l'échec."""
    vrai = socle._effacer_bac_a_sable
    casse = decor["bac"]["id"]

    def sauf_un(conn, portee, pid, *, motif):
        if pid == casse:
            conn.execute("UPDATE projet SET nom = 'à moitié' WHERE id = ?", (pid,))
            raise RuntimeError("panne au milieu")
        return vrai(conn, portee, pid, motif=motif)

    monkeypatch.setattr(socle, "_effacer_bac_a_sable", sauf_un)
    bilan = _outil(tous=True, appliquer=True)
    assert sorted(bilan["effaces"]) == sorted([decor["bac_resp"]["id"],
                                               decor["bac_hugo"]["id"]])
    assert bilan["echecs"] == [{"id": casse, "cause": "RuntimeError: panne au milieu"}]
    assert _sql(decor["db"], "SELECT nom FROM projet WHERE id = ?", (casse,)) == [
        {"nom": "Bac à sable"}]                    # défait, pas à moitié écrit
    monkeypatch.setattr(database, "DB_PATH", decor["db"])
    assert effacer_bacs_a_sable.main(["--tous", "--appliquer"]) == 1
    sortie = capsys.readouterr().out
    assert "NON effacé" in sortie and "1 échec" in sortie


def test_le_verrou_de_l_outil(client, decor):
    (decor["data"] / effacer_bacs_a_sable.NOM_DU_VERROU).write_text("pid 1", encoding="utf-8")
    with pytest.raises(effacer_bacs_a_sable.PassageEnCours):
        _outil(appliquer=True)


def test_les_unites_systemd_lancent_l_outil_toutes_les_heures():
    racine = Path(__file__).resolve().parent.parent / "deploy" / "systemd"
    if not racine.exists():
        pytest.skip(
            "deploy/ est exclu du contexte de build (.dockerignore) : ce test ne tourne QUE "
            "sur la machine de développement. Son skip dans l'image N'EST PAS une couverture "
            "— cf. QA-6, « un skip se lit comme un succès »")
    service = (racine / "bd-bacs-a-sable.service").read_text(encoding="utf-8")
    minuterie = (racine / "bd-bacs-a-sable.timer").read_text(encoding="utf-8")
    assert "Type=oneshot" in service and "User=ubuntu" in service
    assert "ExecStart=/home/ubuntu/BD_ditor/deploy/effacer-bacs-a-sable.sh" in service
    script = (racine.parent / "effacer-bacs-a-sable.sh").read_text(encoding="utf-8")
    assert "docker exec" in script and "tools/effacer_bacs_a_sable.py --appliquer" in script
    assert "Environment=PATH=" in service
    assert "OnCalendar=hourly" in minuterie and "Unit=bd-bacs-a-sable.service" in minuterie
