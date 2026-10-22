"""UX-11 (Hugo, 2026-10-22) — le nom du fichier d'origine, et l'ordre des planches.

Deux remarques de la passe du lot 1. Le numéro d'une planche est son RANG dans l'album : un
dossier mal nommé l'importe dans un ordre que seul l'utilisateur sait faux, et rien ne le
changeait. Et le nom du fichier, seul repère qui reste alors, ne se lisait nulle part.

Ce fichier tient le serveur :
- `GET /api/albums/{id}/planches` dit le NOM du fichier d'origine (`nom_fichier_origine`),
  sans dossier ni préfixe — le reste de `master_origine` reste tu (cf.
  `tests/test_master_origine_tue.py`, qui déclare cette seule exception) ;
- un fichier refusé se dit en mots, et le nomme ;
- `PUT /api/albums/{id}/ordre-des-planches` redistribue les NUMÉROS, jamais les fichiers,
  gardé comme écrire dans l'album, journalisé hors de Ctrl+Z, et refuse par un 409 nommé
  un ordre que l'écran n'avait pas vu ;
- un import APRÈS un réordonnancement n'écrit ni n'efface jamais les fichiers d'une autre
  planche : un numéro et les fichiers qui portent ce numéro ne vont plus ensemble.
"""
import io
import json
import sqlite3

import pytest
from PIL import Image

from conftest import ADMIN, make_png
from pipeline.ingest import nom_du_fichier_d_origine
from test_fonds import (COLLEGUE, IMPORTEUSE, _albums, decor,  # noqa: F401
                        _planche as _planche_fonds)


# ── Le nom du fichier d'origine ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("origine, nom", [
    (None, None),
    ("", None),
    ("page-10.tif", "page-10.tif"),
    ("sharedocs:BD/Mon espace/vol 1/p3.tif", "p3.tif"),
    ("sharedocs:p3.tif", "p3.tif"),
    ("C:\\Users\\moi\\scans\\page 7.tif", "page 7.tif"),
    ("sharedocs:BD/dossier/", None),
    ("   ", None),
])
def test_le_nom_seul_sans_dossier_ni_prefixe(origine, nom):
    assert nom_du_fichier_d_origine(origine) == nom


def _sql(db_path, requete, params=()):
    conn = sqlite3.connect(db_path)
    try:
        lignes = conn.execute(requete, params).fetchall()
        conn.commit()
        return lignes
    finally:
        conn.close()


def _importer(client, album_id, nom, largeur=300, headers=None, **kw):
    r = client.post(f"/api/albums/{album_id}/import", headers=headers or {},
                    files={"file": (nom, make_png(largeur, 200), "image/png")}, **kw)
    assert r.status_code == 201, r.text
    return r.json()


def test_la_liste_des_planches_dit_le_nom_du_fichier_et_rien_de_son_chemin(client, album,
                                                                            db_path):
    a = _importer(client, album["id"], "page-10.png")
    b = _importer(client, album["id"], "page-2.png")
    c = _importer(client, album["id"], "page-3.png")
    _sql(db_path, "UPDATE planches SET master_origine = ? WHERE id = ?",
         ("sharedocs:BD/Espace perso de Léa/page-2.tif", b["id"]))
    _sql(db_path, "UPDATE planches SET master_origine = NULL WHERE id = ?", (c["id"],))
    rep = client.get(f"/api/albums/{album['id']}/planches")
    noms = {p["id"]: p["nom_fichier_origine"] for p in rep.json()}
    assert noms == {a["id"]: "page-10.png", b["id"]: "page-2.tif", c["id"]: None}
    # Le chemin ne sort pas : ni le dossier, ni le préfixe, ni le nom de la colonne.
    assert "Espace perso" not in rep.text and "sharedocs" not in rep.text
    assert "master_origine" not in rep.text


# ── Un fichier refusé se dit en mots ─────────────────────────────────────────────────────

def _refus(client, album, nom, contenu):
    r = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": (nom, contenu, "image/png")})
    assert r.status_code == 400, r.text
    return r.json()["detail"]


def test_un_fichier_qui_n_est_pas_une_image_se_dit_en_mots(client, album):
    detail = _refus(client, album, "page-3.tif", b"ceci n'est pas une image")
    assert detail == ("page-3.tif n'est pas une image lisible : son format n'est pas "
                      "reconnu, ou le fichier est abîmé.")
    # Ce que Pillow disait : un objet Python, sans le nom du fichier.
    assert "BytesIO" not in detail and "cannot identify" not in detail


def test_une_image_tronquee_se_dit_en_mots_et_garde_sa_cause(client, album, data_dir):
    png = make_png(300, 300, "red")
    detail = _refus(client, album, "coupee.png", png[:len(png) // 2])
    assert detail.startswith("coupee.png n'est pas une image lisible : le fichier est "
                             "incomplet ou abîmé ("), detail
    assert "truncated" in detail                    # la cause de Pillow, gardée
    # Rien n'est resté sur le disque : les fichiers réservés sont retirés.
    assert not [f for f in data_dir.rglob("*") if f.is_file()
                and ("corpus" in f.parts or "derivatives" in f.parts)]


def test_un_mode_refuse_nomme_son_fichier(client, album):
    buf = io.BytesIO()
    Image.new("F", (50, 60), 0.5).save(buf, "TIFF")
    detail = _refus(client, album, "flottant.tif", buf.getvalue())
    assert detail.startswith("flottant.tif n'est pas importée : mode d'image « F »"), detail


def test_l_import_sharedocs_dit_le_refus_en_mots(client, album, monkeypatch):
    from pipeline import sharedocs as sd
    monkeypatch.setattr(sd, "download",
                        lambda path, *, principal, compte=None: b"pas une image")
    r = client.post("/api/sharedocs/importer",
                    json={"chemins": ["BD/vol/page-3.tif"], "album_id": album["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["erreurs"] == [{
        "chemin": "BD/vol/page-3.tif",
        "erreur": "page-3.tif n'est pas une image lisible : son format n'est pas reconnu, "
                  "ou le fichier est abîmé."}]


# ── L'ordre des planches ─────────────────────────────────────────────────────────────────

def _ordre(client, album_id, headers=None):
    return [p["id"] for p in client.get(f"/api/albums/{album_id}/planches",
                                        headers=headers or {}).json()]


def _ordonner(client, album_id, ordre, vu, headers=None, geste=None):
    return client.put(f"/api/albums/{album_id}/ordre-des-planches", headers=headers or {},
                      json={"ordre": ordre, "vu": vu, "geste": geste})


def test_reordonner_change_les_numeros_pas_les_fichiers(client, album, db_path):
    ids = [_importer(client, album["id"], f"p{i}.png", 300 + i)["id"] for i in (1, 2, 3)]
    # Un trou dans la numérotation (numéro sauté à l'import) : il reste un trou.
    _sql(db_path, "UPDATE planches SET numero = 7 WHERE id = ?", (ids[2],))
    fichiers = {r[0]: (r[1], r[2]) for r in _sql(
        db_path, "SELECT id, chemin_tiff, chemin_web FROM planches")}
    nouvel = [ids[2], ids[0], ids[1]]
    r = _ordonner(client, album["id"], nouvel, ids, geste="ranger_par_nom")
    assert r.status_code == 200, r.text
    assert r.json() == {"album_id": album["id"], "change": True, "planches": [
        {"id": ids[2], "numero": 1}, {"id": ids[0], "numero": 2}, {"id": ids[1], "numero": 7}]}
    planches = client.get(f"/api/albums/{album['id']}/planches").json()
    assert [p["id"] for p in planches] == nouvel
    assert [p["numero"] for p in planches] == [1, 2, 7]
    # Le numéro éditorial suit le nouvel ordre ; les fichiers n'ont pas bougé.
    assert [p["numero_editorial"] for p in planches] == [1, 2, 3]
    assert {r[0]: (r[1], r[2]) for r in _sql(
        db_path, "SELECT id, chemin_tiff, chemin_web FROM planches")} == fichiers


def test_le_meme_ordre_ne_change_rien_et_n_ecrit_rien_au_journal(client, album, db_path):
    ids = [_importer(client, album["id"], f"p{i}.png")["id"] for i in (1, 2)]
    avant = _sql(db_path, "SELECT COUNT(*) FROM evenement")[0][0]
    r = _ordonner(client, album["id"], ids, ids)
    assert r.status_code == 200 and r.json()["change"] is False
    assert _sql(db_path, "SELECT COUNT(*) FROM evenement")[0][0] == avant


@pytest.mark.parametrize("cas", ["double", "manquante", "etrangere", "vide"])
def test_un_ordre_qui_ne_nomme_pas_chaque_planche_une_fois_est_refuse(client, album, cas):
    ids = [_importer(client, album["id"], f"p{i}.png")["id"] for i in (1, 2, 3)]
    autre = client.post("/api/albums", json={"titre": "Autre"}).json()
    etrangere = _importer(client, autre["id"], "x.png")["id"]
    ordre = {"double": [ids[0], ids[0], ids[1]], "manquante": ids[:2],
             "etrangere": [ids[0], ids[1], etrangere], "vide": []}[cas]
    r = _ordonner(client, album["id"], ordre, ids)
    assert r.status_code == 422, r.text
    assert _ordre(client, album["id"]) == ids


def test_un_acte_par_geste_au_journal_sous_le_document_hors_de_ctrl_z(client, album,
                                                                       db_path):
    ids = [_importer(client, album["id"], f"secret-{i}.png")["id"] for i in (1, 2)]
    r = _ordonner(client, album["id"], ids[::-1], ids, geste="descendre")
    assert r.status_code == 200, r.text
    lignes = _sql(db_path, "SELECT type, cible_table, avant, apres FROM evenement "
                           "WHERE apres LIKE '%ordre%'")
    assert len(lignes) == 1
    type_, cible, avant, apres = lignes[0]
    assert (type_, cible) == ("modification", "document")
    assert json.loads(avant) == {"album_id": album["id"], "acte": "ordre_des_planches",
                                 "ordre": ids}
    assert json.loads(apres) == {"album_id": album["id"], "acte": "ordre_des_planches",
                                 "ordre": ids[::-1], "geste": "descendre"}
    assert "secret" not in avant + apres            # aucun nom de fichier dans la charge
    # Ctrl+Z ne le défait pas : rien d'annulable n'a été fait.
    assert client.get("/api/undo/prochain").json() is None


def test_l_ordre_se_garde_comme_ecrire_dans_l_album(client, db_path, derriere_proxy):
    a = client.post("/api/albums", json={"titre": "Gardé"}, headers=ADMIN).json()
    ids = [_importer(client, a["id"], f"p{i}.png", headers=ADMIN)["id"] for i in (1, 2)]
    cid = _sql(db_path, "SELECT collection_id FROM collection_album WHERE album_id = ?",
               (a["id"],))[0][0]
    bob = {"Remote-User": "bob"}
    _sql(db_path, "INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
                  "VALUES (?, 'utilisateur', 'bob', 'lecture')", (cid,))
    assert _ordre(client, a["id"], bob) == ids              # bob lit l'album
    r = _ordonner(client, a["id"], ids[::-1], ids, headers=bob)
    assert r.status_code == 404, r.text                     # une donnée : « 404, jamais 403 »
    assert _ordre(client, a["id"], ADMIN) == ids
    _sql(db_path, "UPDATE collection_acces SET niveau = 'ecriture' WHERE principal = 'bob'")
    r = _ordonner(client, a["id"], ids[::-1], ids, headers=bob)
    assert r.status_code == 200, r.text
    assert _ordre(client, a["id"], ADMIN) == ids[::-1]


def test_deux_personnes_qui_reordonnent_en_meme_temps_la_seconde_recoit_un_409_nomme(
        client, db_path, derriere_proxy):
    a = client.post("/api/albums", json={"titre": "Partagé"}, headers=ADMIN).json()
    ids = [_importer(client, a["id"], f"p{i}.png", headers=ADMIN)["id"] for i in (1, 2, 3)]
    alice = {"Remote-User": "alice", "Remote-Name": "Alice Martin",
             "Remote-Groups": "bd-admins"}
    bob = {"Remote-User": "bob", "Remote-Groups": "bd-admins"}
    assert client.get("/api/moi", headers=alice).status_code == 200   # son nom, en miroir
    vu_par_bob = _ordre(client, a["id"], bob)
    r = _ordonner(client, a["id"], [ids[1], ids[0], ids[2]], ids, headers=alice)
    assert r.status_code == 200, r.text
    r = _ordonner(client, a["id"], [ids[0], ids[2], ids[1]], vu_par_bob, headers=bob)
    assert r.status_code == 409, r.text
    d = r.json()["detail"]
    assert d["message"].startswith("Conflit : l'ordre des planches a été changé par "
                                   "Alice Martin, le "), d["message"]
    assert d["message"].endswith("Votre modification n'est pas enregistrée.")
    assert d["conflit"]["valeur_actuelle"] == [ids[1], ids[0], ids[2]]
    assert d["conflit"]["auteur"]["login"] == "alice"
    assert _ordre(client, a["id"], ADMIN) == [ids[1], ids[0], ids[2]]   # rien d'écrasé
    # Une planche entrée depuis que bob a regardé : l'ensemble a changé, et c'est dit.
    vu_par_bob = _ordre(client, a["id"], bob)
    _importer(client, a["id"], "p4.png", headers=alice)
    r = _ordonner(client, a["id"], vu_par_bob[::-1], vu_par_bob, headers=bob)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["message"].startswith(
        "Conflit : des planches ont été ajoutées ou supprimées par Alice Martin, le ")


def test_l_ordre_actuel_se_lit_sous_le_verrou_d_ecriture(client, album, db_path):
    """Une AUTRE écriture de l'ordre est en cours (une transaction ouverte, pas encore
    validée) quand la requête arrive. Lue hors transaction, la garde voyait l'ordre d'avant,
    passait, puis écrasait l'autre une fois son verrou rendu. Sous `BEGIN IMMEDIATE`, la
    requête attend que l'autre ait validé, lit l'ordre nouveau, et refuse."""
    import threading
    import time
    ids = [_importer(client, album["id"], f"p{i}.png")["id"] for i in (1, 2, 3)]
    autre = sqlite3.connect(db_path, timeout=5)
    try:
        autre.execute("BEGIN IMMEDIATE")
        autre.execute("UPDATE planches SET numero = -numero WHERE album_id = ?", (album["id"],))
        for numero, pid in zip((1, 2, 3), (ids[2], ids[1], ids[0])):
            autre.execute("UPDATE planches SET numero = ? WHERE id = ?", (numero, pid))
        reponse = {}
        fil = threading.Thread(target=lambda: reponse.setdefault(
            "r", _ordonner(client, album["id"], [ids[1], ids[0], ids[2]], ids)))
        fil.start()
        time.sleep(0.5)
        autre.commit()
        fil.join(10)
    finally:
        autre.close()
    assert reponse["r"].status_code == 409, reponse["r"].text
    assert _ordre(client, album["id"]) == ids[::-1]       # l'autre écriture a tenu


# ── Un import après un réordonnancement ──────────────────────────────────────────────────

def _empreintes(data_dir):
    return {f.relative_to(data_dir).as_posix(): f.read_bytes()
            for f in data_dir.rglob("*") if f.is_file()
            and ("corpus" in f.parts or "derivatives" in f.parts)}


def test_un_import_apres_un_reordonnancement_ne_touche_aucun_fichier_d_une_autre_planche(
        client, album, db_path, data_dir):
    """A et B échangent leurs numéros : A porte le 2 et les fichiers `planche_0001.*`, B le
    1 et `planche_0002.*`. On détruit A, qui avait le plus GRAND numéro : le prochain numéro
    libre de l'album redevient 2 — et les fichiers `planche_0002.*` sont ceux de B. L'import
    doit les sauter, et un numéro imposé qui les désigne doit être refusé."""
    pa = _importer(client, album["id"], "a.png", 310)
    pb = _importer(client, album["id"], "b.png", 320)
    assert _ordonner(client, album["id"], [pb["id"], pa["id"]],
                     [pa["id"], pb["id"]]).status_code == 200
    chemins_b = _sql(db_path, "SELECT chemin_tiff, chemin_web FROM planches WHERE id = ?",
                     (pb["id"],))[0]
    assert all("planche_0002" in c for c in chemins_b), chemins_b
    assert client.delete(f"/api/planches/{pa['id']}").status_code == 204
    avant = _empreintes(data_dir)
    assert set(chemins_b) <= set(avant)

    # Un numéro imposé qui désigne les fichiers de B, ou le numéro de B : refusés.
    for numero in (1, 2):
        r = client.post(f"/api/albums/{album['id']}/import", data={"numero": str(numero)},
                        files={"file": ("c.png", make_png(330, 200), "image/png")})
        assert r.status_code == 409, (numero, r.text)
    assert _empreintes(data_dir) == avant

    # Un numéro libre : ni le 1 (B), ni le 2 (les fichiers de B).
    pc = _importer(client, album["id"], "c.png", 330)
    assert pc["numero"] == 3
    apres = _empreintes(data_dir)
    assert {k: v for k, v in apres.items() if k in avant} == avant    # rien de réécrit
    assert set(avant) <= set(apres)                                     # rien d'effacé
    planches = client.get(f"/api/albums/{album['id']}/planches").json()
    assert [(p["id"], p["largeur_px"]) for p in planches] == [(pb["id"], 320), (pc["id"], 330)]


# ── Réordonner n'est pas un travail sur l'album (Hugo, 2026-10-22) ───────────────────────

def test_reordonner_l_album_d_une_autre_ne_lui_interdit_pas_de_le_supprimer_seule(
        client, db_path, decor):  # noqa: F811
    """Un ↓ d'une collègue laissait l'importatrice DEMANDER la suppression d'un album où
    personne d'autre n'avait rien annoté : l'acte, écrit sous le document, comptait comme un
    travail d'autrui. Il ne compte plus — ni pour la règle, ni dans ce que l'administrateur
    lit sous une demande —, et une validation, elle, compte toujours."""
    import autorisation
    aid = decor["erreur"]
    _planche_fonds(client, aid, IMPORTEUSE)
    assert _albums(client, IMPORTEUSE)[aid]["destructible"] is True
    ids = _ordre(client, aid, COLLEGUE)
    r = _ordonner(client, aid, ids[::-1], ids, headers=COLLEGUE, geste="descendre")
    assert r.status_code == 200, r.text
    assert _albums(client, IMPORTEUSE)[aid]["destructible"] is True
    n = len(autorisation._sources_du_travail("?"))
    agents = [r[0] for r in _sql(
        db_path, f"SELECT agent FROM ({autorisation.sql_actes_sur_album('?')})", [aid] * n)]
    assert "collegue" not in agents, agents
    # La règle mord encore : un vrai travail de la collègue compte.
    r = client.patch(f"/api/planches/{ids[0]}/validation", headers=COLLEGUE,
                     json={"validee": True})
    assert r.status_code == 200, r.text
    assert _albums(client, IMPORTEUSE)[aid]["destructible"] is False


# ── Les refus qui ne sont pas la faute du fichier (relecture croisée) ────────────────────

def test_un_decodeur_absent_du_serveur_ne_se_dit_pas_fichier_abime(client, album,
                                                                   monkeypatch, data_dir):
    from PIL import Image as Img
    buf = io.BytesIO()
    Img.new("RGB", (60, 40), "red").save(buf, "JPEG")
    monkeypatch.delattr(Img.core, "jpeg_decoder")
    r = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("page.jpg", buf.getvalue(), "image/jpeg")})
    assert r.status_code == 503, r.text
    detail = r.json()["detail"]
    assert detail.startswith("page.jpg n'est pas importée : ce serveur ne sait pas décoder "
                             "son format"), detail
    assert "abîmé" not in detail and "not available" not in detail
    assert not [f for f in data_dir.rglob("*") if f.is_file()
                and ("corpus" in f.parts or "derivatives" in f.parts)]


@pytest.mark.parametrize("err, cause", [
    (28, "le disque du serveur est plein"),            # ENOSPC
    (13, "le serveur n'a pas le droit d'écrire ses images"),   # EACCES
    (5, "le serveur n'a pas pu écrire l'image sur son disque"),  # EIO
])
def test_une_ecriture_ratee_repond_507_sans_chemin_serveur(client, album, monkeypatch,
                                                            data_dir, err, cause):
    from pipeline import ingest

    def ratee(*a, **k):
        raise OSError(err, "No space left on device", "/data/corpus/album_1/secret.jpg")
    monkeypatch.setattr(ingest, "ecrire_copie_de_travail", ratee)
    r = client.post(f"/api/albums/{album['id']}/import",
                    files={"file": ("page.png", make_png(), "image/png")})
    assert r.status_code == 507, r.text
    detail = r.json()["detail"]
    assert detail == (f"page.png n'a pas été importée : {cause}. Rien n'est entré ; "
                      "prévenez l'administrateur de l'instance avant de réessayer.")
    assert "/data" not in r.text and "secret" not in r.text
    assert client.get(f"/api/albums/{album['id']}/planches").json() == []
    assert not [f for f in data_dir.rglob("*") if f.is_file()
                and ("corpus" in f.parts or "derivatives" in f.parts)]


def test_l_import_sharedocs_s_arrete_sur_une_ecriture_ratee(client, album, monkeypatch):
    from pipeline import ingest
    from pipeline import sharedocs as sd
    monkeypatch.setattr(sd, "download",
                        lambda path, *, principal, compte=None: make_png())

    def ratee(*a, **k):
        raise OSError(28, "No space left on device", "/data/corpus/album_1/secret.jpg")
    monkeypatch.setattr(ingest, "ecrire_copie_de_travail", ratee)
    r = client.post("/api/sharedocs/importer", json={
        "chemins": ["BD/p1.tif", "BD/p2.tif", "BD/p3.tif"], "album_id": album["id"]})
    assert r.status_code == 200, r.text
    erreurs = r.json()["erreurs"]
    assert [e["chemin"] for e in erreurs] == ["BD/p1.tif", "BD/p2.tif", "BD/p3.tif"]
    assert erreurs[0]["erreur"].startswith("p1.tif n'a pas été importée : le disque du "
                                           "serveur est plein.")
    assert all(e["erreur"].startswith("non importé") for e in erreurs[1:])
    assert "/data" not in r.text and "secret" not in r.text


def test_une_image_trop_grande_se_dit_en_francais(client, album, monkeypatch):
    from PIL import Image as Img
    monkeypatch.setattr(Img, "MAX_IMAGE_PIXELS", 1000)
    detail = _refus(client, album, "geante.png", make_png(100, 100))
    assert detail == ("geante.png n'est pas importée : l'image est trop grande pour être "
                      "ouverte — plus de 2000 pixels, la limite de ce serveur."), detail
    assert "Image size" not in detail and "decompression" not in detail.lower()
