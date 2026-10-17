"""COL-3, tranche 3 — ce que la tranche 2 avait écrit pour UNE copie, réécrit pour deux.

Un document n'avait qu'une copie de travail, et plusieurs sites du code s'en contentaient :
ils marchaient parce que « le document » et « la copie » désignaient la même chose. La
tranche 3 fera naître des copies SŒURS (le même document, une seconde ligne `albums`, ses
planches pointant vers les mêmes fichiers — décision D6). Ces sites sont réécrits avant la
première sœur (cadrage, « Ce que la tranche 2 avait écrit pour UNE copie, et qui casse à
deux »), et chacun est éprouvé ici sur une sœur posée par SQL — la route qui en fera naître
n'existe pas encore, c'est le commit suivant :

- une demande de suppression se cherche par COPIE, pas par document : sinon la copie d'un
  autre projet afficherait « suppression demandée » pour un geste fait ailleurs ;
- accepter une demande ne détruit que la copie DEMANDÉE (D5) ;
- « personne d'autre n'y a travaillé » ne lit, parmi les actes sous le document, que ceux
  qui nomment CET album ;
- « l'avoir importé » se lit sur la copie (`copie.creee_par`) : « a créé CETTE copie » ;
- détruire une copie, ou l'une de ses planches, n'efface pas un fichier qu'une sœur emploie
  encore ; la dernière copie emporte tout.

Le décor : `lea` importe « Le Lotus bleu » dans Principale (projet de repli) et y pose une
planche ; une sœur vit dans « Étude », d'un second projet, créée par `sam`, qui y écrit ;
`lectrice` lit Étude, et rien d'autre.
"""
import sqlite3

import pytest

import database
from conftest import ADMIN
from test_fonds import (_accorder, _album, _albums, _collection, _demander, _fichiers,
                        _planche, _repondre)
from test_projets import _sql

LEA = {"Remote-User": "lea"}
SAM = {"Remote-User": "sam"}
LECTRICE = {"Remote-User": "lectrice"}


def _soeur(db_path, album_id, collection_id, *, creee_par):
    """Une seconde copie du document de `album_id`, rangée dans `collection_id`, ses
    planches pointant vers les MÊMES fichiers (D6). Ce que `database.creer_copie` fera au
    commit suivant, posé ici à la main : sans elle, rien ne distinguerait « le document » de
    « la copie », et ce fichier n'éprouverait rien."""
    c = sqlite3.connect(db_path)
    try:
        titre, document_id = c.execute("SELECT titre, document_id FROM albums WHERE id = ?",
                                       (album_id,)).fetchone()
        projet = c.execute(f"SELECT {database.sql_projet_de('c')} FROM collection c "
                           "WHERE c.id = ?", (collection_id,)).fetchone()[0]
        b = c.execute("INSERT INTO albums (titre, document_id, projet_id) VALUES (?, ?, ?)",
                      (titre, document_id, projet)).lastrowid
        c.execute("INSERT INTO copie (album_id, creee_par, cran, depuis_album_id) "
                  "VALUES (?, ?, 'images', ?)", (b, creee_par, album_id))
        c.execute("INSERT INTO planches (album_id, numero, role, chemin_tiff, chemin_web, "
                  "largeur_px, hauteur_px) SELECT ?, numero, role, chemin_tiff, chemin_web, "
                  "largeur_px, hauteur_px FROM planches WHERE album_id = ?", (b, album_id))
        c.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                  (collection_id, b))
        c.commit()
        return b
    finally:
        c.close()


def _chemins(db_path, album_id):
    return [(r["chemin_tiff"], r["chemin_web"]) for r in _sql(
        db_path, "SELECT chemin_tiff, chemin_web FROM planches WHERE album_id = ? "
                 "ORDER BY numero", (album_id,))]


@pytest.fixture
def soeurs(client, derriere_proxy, data_dir, db_path):
    principale = _collection(client, "Principale")
    r = client.post("/api/projets", json={"nom": "Étude B"}, headers=ADMIN)
    assert r.status_code == 201, r.text
    etude = _collection(client, "Étude", projet_id=r.json()["id"])
    _accorder(client, principale, "lea", "ecriture")
    _accorder(client, etude, "sam", "ecriture")
    _accorder(client, etude, "lectrice", "lecture")
    a = _album(client, "Le Lotus bleu", principale, LEA)
    pa = _planche(client, a, LEA)
    b = _soeur(db_path, a, etude, creee_par="sam")
    pb = _sql(db_path, "SELECT id FROM planches WHERE album_id = ?", (b,))[0]["id"]
    return {"principale": principale, "etude": etude, "a": a, "b": b, "pa": pa, "pb": pb,
            "data": data_dir}


# --------------------------------------------------------------------------- #
# Les fichiers d'une sœur (D6) — le risque irréversible
# --------------------------------------------------------------------------- #
def _existe(data_dir, chemins):
    return [(data_dir / t).exists() and (data_dir / w).exists() for t, w in chemins]


def test_detruire_une_copie_garde_les_images_de_sa_soeur(client, db_path, soeurs):
    """La copie A est détruite ; la sœur B emploie ses fichiers : ils restent sur le disque,
    l'image de B répond encore, et le document vit avec B. Détruire B, la dernière, emporte
    les fichiers et élague les dossiers vides de A."""
    a, b, data = soeurs["a"], soeurs["b"], soeurs["data"]
    chemins = _chemins(db_path, b)
    assert chemins == _chemins(db_path, a) and all(_existe(data, chemins))
    doc = _sql(db_path, "SELECT document_id FROM albums WHERE id = ?", (a,))[0]["document_id"]

    assert client.delete(f"/api/albums/{a}", headers=ADMIN).status_code == 204
    assert all(_existe(data, chemins)), "une image employée par la sœur a été effacée"
    web = chemins[0][1]
    assert client.get("/" + web, headers=SAM).status_code == 200
    assert _sql(db_path, "SELECT 1 FROM document WHERE id = ?", (doc,)) == [{"1": 1}]

    assert client.delete(f"/api/albums/{b}", headers=ADMIN).status_code == 204
    assert not any((data / t).exists() or (data / w).exists() for t, w in chemins)
    assert _fichiers(data, a) == [] and _fichiers(data, b) == []
    assert _sql(db_path, "SELECT 1 FROM document WHERE id = ?", (doc,)) == []


def test_detruire_une_copie_seule_efface_tout_son_dossier(client, db_path, soeurs):
    """Sans sœur qui l'emploie, rien ne change : le dossier part en entier, y compris un
    fichier qu'aucune planche ne désigne (un master orphelin d'un import raté)."""
    c = _album(client, "Seul", soeurs["principale"], LEA)
    _planche(client, c, LEA)
    orphelin = soeurs["data"] / "corpus" / f"album_{c}" / "orphelin.tif"
    orphelin.write_bytes(b"x")
    assert client.delete(f"/api/albums/{c}", headers=ADMIN).status_code == 204
    assert _fichiers(soeurs["data"], c) == []


def test_supprimer_une_planche_garde_le_fichier_de_la_soeur(client, db_path, soeurs):
    data = soeurs["data"]
    chemins = _chemins(db_path, soeurs["a"])
    assert client.delete(f"/api/planches/{soeurs['pa']}", headers=ADMIN).status_code == 204
    assert all(_existe(data, chemins)), "le fichier de la planche sœur a été effacé"
    assert client.delete(f"/api/planches/{soeurs['pb']}", headers=ADMIN).status_code == 204
    assert not any((data / t).exists() or (data / w).exists() for t, w in chemins)


# --------------------------------------------------------------------------- #
# La demande se cherche par COPIE
# --------------------------------------------------------------------------- #
def test_une_demande_sur_une_copie_ne_se_lit_pas_sur_sa_soeur(client, soeurs):
    """Le geste fait dans le projet de A ne s'affiche pas sur B, que lit une personne qui
    n'entre pas dans le projet de A : ce serait une fuite entre projets, et un faux."""
    a, b = soeurs["a"], soeurs["b"]
    _accorder(client, soeurs["principale"], "sam", "ecriture")
    assert _demander(client, a, SAM).status_code == 201
    assert _albums(client, ADMIN)[a]["demande"] is not None
    assert _albums(client, ADMIN)[b]["demande"] is None
    assert _albums(client, LECTRICE)[b]["demande"] is None
    # Et la même suppression sur la sœur n'est pas « déjà demandée » : c'est une autre copie.
    _accorder(client, soeurs["etude"], "lea", "ecriture")
    assert _demander(client, b, LEA).status_code == 201


def test_accepter_ne_detruit_que_la_copie_demandee(client, db_path, soeurs):
    """D5 — l'administrateur qui accepte la demande faite sur A ne détruit que A : B garde
    ses planches, ses fichiers, son document."""
    a, b = soeurs["a"], soeurs["b"]
    _accorder(client, soeurs["principale"], "sam", "ecriture")
    demande = _demander(client, a, SAM).json()["id"]
    assert _repondre(client, demande, "acceptee").status_code == 200
    assert _sql(db_path, "SELECT id FROM albums WHERE id IN (?, ?)", (a, b)) == [{"id": b}]
    assert _sql(db_path, "SELECT COUNT(*) AS n FROM planches WHERE album_id = ?",
                (b,)) == [{"n": 1}]
    assert all(_existe(soeurs["data"], _chemins(db_path, b)))
    vue = [d for d in client.get("/api/demandes", headers=ADMIN).json()
           if d["id"] == demande][0]
    assert vue["reponse"] == "acceptee"


def test_detruire_une_copie_ne_repond_pas_a_la_demande_de_sa_soeur(client, soeurs):
    """Une destruction clôt les demandes qui visaient CETTE copie : celle déposée sur la
    sœur attend toujours sa réponse — la copie qu'elle vise vit encore."""
    a, b = soeurs["a"], soeurs["b"]
    _accorder(client, soeurs["etude"], "lea", "ecriture")
    _accorder(client, soeurs["principale"], "sam", "ecriture")
    sur_a = _demander(client, a, SAM).json()["id"]
    sur_b = _demander(client, b, LEA).json()["id"]
    assert client.delete(f"/api/albums/{a}", headers=ADMIN).status_code == 204
    vues = {d["id"]: d for d in client.get("/api/demandes", headers=ADMIN).json()}
    assert (vues[sur_a]["reponse"], vues[sur_b]["reponse"]) == ("acceptee", None)
    assert _albums(client, ADMIN)[b]["demande"]["id"] == sur_b


def test_la_demande_designe_sa_copie(client, soeurs):
    """`copie`, dans la vue d'une demande, est la copie d'où le geste est parti — pas « le
    plus petit album du document », qui désigne une copie au hasard dès qu'il y en a deux."""
    _accorder(client, soeurs["etude"], "lea", "ecriture")
    demande = _demander(client, soeurs["b"], LEA).json()["id"]
    vue = [d for d in client.get("/api/demandes", headers=ADMIN).json()
           if d["id"] == demande][0]
    assert [x["copie"] for x in vue["documents"]] == [soeurs["b"]]


def test_le_travail_montre_sous_une_demande_est_celui_de_sa_copie(client, soeurs):
    """Sous une demande sur B, l'administrateur voit le travail fait sur B — pas celui
    qu'une autre copie, dans un autre projet, a reçu (ici la notice de A, retouchée par un
    administrateur)."""
    a, b = soeurs["a"], soeurs["b"]
    assert client.put(f"/api/albums/{a}", json={"titre": "Notice retouchée"},
                      headers=ADMIN).status_code == 200
    _accorder(client, soeurs["etude"], "lea", "ecriture")
    demande = _demander(client, b, LEA)
    assert demande.status_code == 201, demande.text
    vue = [d for d in client.get("/api/demandes", headers=ADMIN).json()
           if d["id"] == demande.json()["id"]][0]
    assert [e["agent"] for e in vue["documents"][0]["travail_des_autres"]] == []


# --------------------------------------------------------------------------- #
# Supprimer définitivement une copie qu'on a CRÉÉE
# --------------------------------------------------------------------------- #
def test_qui_a_cree_la_copie_la_supprime_seul(client, soeurs):
    """« L'avoir importé » se lit sur la copie : `sam` a créé B, seul à y avoir travaillé,
    il écrit dans toutes ses collections — il la supprime sans rien demander, bien que le
    document ait été importé par `lea`. Et `lea`, qui écrit aussi dans Étude, ne supprime
    pas seule une copie qu'elle n'a pas créée."""
    b = soeurs["b"]
    assert _albums(client, SAM)[b]["destructible"] is True
    _accorder(client, soeurs["etude"], "lea", "ecriture")
    assert _albums(client, LEA)[b]["destructible"] is False
    assert client.delete(f"/api/albums/{b}", headers=LEA).status_code == 403
    assert client.delete(f"/api/albums/{b}", headers=SAM).status_code == 204


def test_le_travail_sur_une_soeur_ne_retient_pas_la_copie(client, soeurs):
    """La notice de A retouchée par `lea` s'écrit sous le DOCUMENT, l'album A dans la charge.
    Ce n'est pas un travail sur B : `sam` la supprime encore seul."""
    a, b = soeurs["a"], soeurs["b"]
    assert client.put(f"/api/albums/{a}", json={"titre": "Notice retouchée"},
                      headers=LEA).status_code == 200
    assert _albums(client, SAM)[b]["destructible"] is True
    # Le même geste sur B, par une autre, la retient.
    _accorder(client, soeurs["etude"], "lea", "ecriture")
    assert client.put(f"/api/albums/{b}", json={"titre": "Retouchée par Léa"},
                      headers=LEA).status_code == 200
    assert _albums(client, SAM)[b]["destructible"] is False


# --------------------------------------------------------------------------- #
# Un import n'écrit jamais sur l'image d'une sœur (relecture croisée de la v31)
# --------------------------------------------------------------------------- #
def _autre_png():
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (200, 10, 10)).save(buf, "PNG")
    return buf.getvalue()


def _images(data, chemins):
    return [((data / t).read_bytes(), (data / w).read_bytes()) for t, w in chemins]


def _planche_de_a_supprimee(client, db_path, soeurs):
    """La planche de A supprimée : ses fichiers RESTENT, la sœur B les désigne — et le
    numéro 1 est de nouveau libre dans A. Rend ce que B emploie, et ses octets."""
    chemins = _chemins(db_path, soeurs["b"])
    avant = _images(soeurs["data"], chemins)
    assert client.delete(f"/api/planches/{soeurs['pa']}", headers=ADMIN).status_code == 204
    assert _images(soeurs["data"], chemins) == avant, "prémisse : les fichiers sont gardés"
    return chemins, avant


def test_reimporter_dans_la_copie_source_n_ecrase_pas_l_image_d_une_soeur(client, db_path,
                                                                         soeurs):
    """Recopié de la relecture croisée (`tests/test_relecture_t3a.py`, branche `relecture`,
    `e6473a5`). Le numéro « libre sans écraser » (DB-1) ne regardait que les planches de
    l'album qui importe : le dérivé et le master du nouvel import étaient écrits À LA PLACE
    de ceux de B. Le numéro saute désormais au premier dont les fichiers ne sont pas pris."""
    chemins, avant = _planche_de_a_supprimee(client, db_path, soeurs)
    r = client.post(f"/api/albums/{soeurs['a']}/import", headers=ADMIN,
                    files={"file": ("p.png", _autre_png(), "image/png")})
    assert r.status_code == 201, r.text
    assert _images(soeurs["data"], chemins) == avant, \
        "l'image de la copie sœur a été remplacée par celle d'un autre import"
    assert r.json()["numero"] == 2 and r.json()["chemin_web"] not in {w for _t, w in chemins}


def test_un_import_qui_echoue_n_efface_pas_l_image_d_une_soeur(client, db_path, soeurs):
    """L'ingestion échoue (un contenu qui n'est pas une image) : le master écrit par CET
    import est retiré — et c'était, avant, le fichier de B, d'abord écrasé, puis effacé."""
    chemins, avant = _planche_de_a_supprimee(client, db_path, soeurs)
    r = client.post(f"/api/albums/{soeurs['a']}/import", headers=ADMIN,
                    files={"file": ("p.png", b"pas une image", "image/png")})
    assert r.status_code == 400, r.text
    assert _images(soeurs["data"], chemins) == avant


def test_un_numero_explicite_dont_les_images_servent_est_refuse(client, db_path, soeurs):
    chemins, avant = _planche_de_a_supprimee(client, db_path, soeurs)
    r = client.post(f"/api/albums/{soeurs['a']}/import", headers=ADMIN,
                    data={"numero": "1"},
                    files={"file": ("p.png", _autre_png(), "image/png")})
    assert r.status_code == 409 and "numéro 1" in r.json()["detail"], r.text
    assert _images(soeurs["data"], chemins) == avant


def test_un_lot_defait_n_efface_pas_l_image_d_une_soeur(client, db_path, soeurs,
                                                        monkeypatch):
    """Un import ShareDocs dont la fin échoue est défait, et il retire les fichiers qu'il a
    écrits : ceux de SES planches, qu'aucune ligne ne désigne plus — avant, ceux de B."""
    import main
    import pipeline.sharedocs as sd
    from fastapi.testclient import TestClient
    chemins, avant = _planche_de_a_supprimee(client, db_path, soeurs)
    monkeypatch.setattr(sd, "download",
                        lambda path, *, principal, compte=None: _autre_png())

    def panne(*a, **k):
        raise RuntimeError("panne après l'ingestion")
    monkeypatch.setattr(main, "_journaliser_scan", panne)
    sans_relance = TestClient(main.app, headers={main.EN_TETE_REQUETE: "1"},
                              raise_server_exceptions=False)
    r = sans_relance.post("/api/sharedocs/importer", headers=ADMIN,
                          json={"chemins": ["BD/p1.png"], "album_id": soeurs["a"]})
    assert r.status_code == 500, r.text
    assert _images(soeurs["data"], chemins) == avant


def test_un_fichier_laisse_sur_le_disque_fait_sauter_le_numero(client, soeurs):
    """Le disque seul : un master que plus aucune planche ne désigne — un ménage qui a
    échoué — n'est pas réécrit ; le numéro passe au suivant."""
    orphelin = soeurs["data"] / "corpus" / f"album_{soeurs['a']}" / "planche_0002.png"
    orphelin.write_bytes(b"ORPHELIN")
    r = client.post(f"/api/albums/{soeurs['a']}/import", headers=ADMIN,
                    files={"file": ("p.png", _autre_png(), "image/png")})
    assert r.status_code == 201 and r.json()["numero"] == 3, r.text
    assert orphelin.read_bytes() == b"ORPHELIN"


def test_un_chemin_designe_fait_sauter_le_numero_meme_sans_fichier(client, db_path, soeurs):
    """La base seule : B désigne encore des chemins dont les fichiers ont disparu du disque.
    Un import ne vient pas les recréer sous une autre image."""
    chemins, _avant = _planche_de_a_supprimee(client, db_path, soeurs)
    for t, w in chemins:
        (soeurs["data"] / t).unlink()
        (soeurs["data"] / w).unlink()
    r = client.post(f"/api/albums/{soeurs['a']}/import", headers=ADMIN,
                    files={"file": ("p.png", _autre_png(), "image/png")})
    assert r.status_code == 201 and r.json()["numero"] == 2, r.text
    assert not any((soeurs["data"] / t).exists() for t, _w in chemins)


# --------------------------------------------------------------------------- #
# Ce qu'une destruction efface d'après la base : des images d'album, et rien d'autre
# --------------------------------------------------------------------------- #
def test_un_chemin_retouche_ne_fait_rien_effacer_hors_des_images(client, db_path, soeurs):
    """Les fichiers qu'une copie emploie ailleurs que dans ses dossiers s'effacent d'après
    la base. Un chemin retouché à la main — qui remonte par `..`, ou absolu — ne fait rien
    effacer : seul passe `corpus|derivatives/album_<N>/<fichier>`, résolu sous ces dossiers."""
    data = soeurs["data"]
    remonte, absolu = data / "sentinelle.txt", data / "hors" / "absolu.txt"
    absolu.parent.mkdir()
    for f in (remonte, absolu):
        f.write_bytes(b"A GARDER")
    _sql(db_path, "UPDATE planches SET chemin_tiff = ?, chemin_web = ? WHERE id = ?",
         ("corpus/../sentinelle.txt", str(absolu), soeurs["pb"]))
    assert client.delete(f"/api/albums/{soeurs['a']}", headers=ADMIN).status_code == 204
    assert client.delete(f"/api/albums/{soeurs['b']}", headers=ADMIN).status_code == 204
    assert remonte.read_bytes() == b"A GARDER" and absolu.read_bytes() == b"A GARDER"


def test_sans_forme_relative_rien_n_est_efface(client, db_path, soeurs, monkeypatch, caplog):
    """Les dossiers d'un album sans forme relative à la racine de données ne se recoupent
    pas avec la base : on ne sait pas ce qu'une sœur emploie. Rien n'est effacé — le
    dossier entier partait — et le journal du serveur le dit."""
    import socle

    def hors_racine(album_id):
        raise ValueError("hors de la racine")
    monkeypatch.setattr(socle, "dossiers_d_album", hors_racine)
    chemins = _chemins(db_path, soeurs["b"])
    avant = _images(soeurs["data"], chemins)
    with caplog.at_level("WARNING", logger="bd_annotator"):
        assert client.delete(f"/api/albums/{soeurs['a']}", headers=ADMIN).status_code == 204
    assert _images(soeurs["data"], chemins) == avant
    assert _fichiers(soeurs["data"], soeurs["a"]), "le dossier de A a été effacé"
    assert any("restent sur le disque" in r.getMessage() for r in caplog.records)
