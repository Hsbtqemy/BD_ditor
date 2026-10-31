"""H4 (ANN-7, tranche 2 ; Hugo, 2026-10-27) — chaque bac à sable naît avec une grille fictive.

Elle vient d'un tableur FICTIF du dépôt (`config.GRILLE_DU_BAC`, le modèle du format) et non
du code. Ces tests tiennent, en une phrase par bloc :

- la naissance : publiée, active, propre à ce bac à sable, et la page peut y poser sans aucune
  autre action ;
- la fin : la remise à neuf rend une grille neuve sans relevé, l'effacement emporte tout,
  sans orphelin dans aucune des seize tables ;
- le fichier absent ou refusé : le bac à sable naît sans grille, et le serveur le dit ;
- l'isolement : personne d'autre ne la lit, administrateur compris, et rien n'en sort ;
- le journal : ses actes ne comptent pour personne ;
- l'image : le fichier est dans ce que l'image copie. Toute la suite tournant aussi DANS
  l'image (`deploy/Dockerfile`, étape `test`, le même `COPY . .`), un fichier perdu y ferait
  tomber le premier bloc.
"""
import fnmatch
import logging
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import autorisation
import comptes
import config
import database
import grille_import
import socle
from conftest import REPO_ROOT
from grilles_decor import MODELE, MODELE_LISTES, flux, importer, ok
from test_jeu import DOC_EXEMPLE, DOC_PARCOURS, ecrire_jeu

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import _commun  # noqa: E402
import preparer_jeu  # noqa: E402

LEA = {"Remote-User": "lea", "Remote-Groups": ""}
SAM = {"Remote-User": "sam", "Remote-Groups": ""}
RITA = {"Remote-User": "rita", "Remote-Groups": ""}
HUGO = {"Remote-User": "hugo", "Remote-Groups": "bd-admins"}

NOM = config.GRILLE_DU_BAC_NOM


def _sql(q, p=()):
    c = sqlite3.connect(database.DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        r = [dict(x) for x in c.execute(q, p)]
        c.commit()
        return r
    finally:
        c.close()


def _comptes():
    return {t: _sql(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"]
            for t in database.TABLES_DES_GRILLES}


@pytest.fixture
def jeu(client, tmp_path, derriere_proxy):
    depot = ecrire_jeu(tmp_path / "jeu-depot", [DOC_PARCOURS, DOC_EXEMPLE],
                       images=("p1.png", "p2.png"))
    conn = database.get_connection()
    try:
        preparer_jeu.preparer(conn, depot=depot, appliquer_=True, dire=lambda _l: None)
    finally:
        conn.close()
    for qui in (LEA, SAM, RITA, HUGO):
        client.get("/api/moi", headers=qui)


def _ouvrir(client, qui=LEA):
    return ok(client.post("/api/bac-a-sable", headers=qui), 201)


def _active(client, projet, qui=LEA):
    actives = ok(client.get(f"/api/projets/{projet}/grilles", headers=qui))["actives"]
    assert len(actives) == 1, actives
    return actives[0]


def _bulle(client, bac, qui=LEA):
    """La bulle « LE OTAGE » de la copie de l'exemple, au cran `transcription`."""
    copie = next(j for j in bac["jeu"] if j["role"] == "exemple")
    pl = copie["planche_ids"][0]
    regions = ok(client.get(f"/api/planches/{pl}/regions", headers=qui))
    return pl, next(r["id"] for r in regions if r["type"] == "bulle")


def _poser(client, grille, qui=LEA, **cible):
    return ok(client.post("/api/releves", headers=qui, json={
        "grille_id": grille["id"], "version": grille["version"]["numero"], **cible}), 201)


# --------------------------------------------------------------------------- #
# Naître
# --------------------------------------------------------------------------- #
def test_le_modele_passe_la_validation_sans_avertissement():
    """Le fichier qu'on lit à chaque naissance : une anomalie y priverait tous les bacs à
    sable de grille, et un avertissement y dirait que le modèle ne dit plus ce qu'on croit."""
    lu = grille_import.lire(flux(MODELE), flux(MODELE_LISTES),
                            porte_sur=config.GRILLE_DU_BAC_PORTE_SUR)
    assert lu["anomalies"] == [] and lu["avertissements"] == []


def test_il_nait_avec_une_grille_publiee_active_et_a_lui(client, jeu):
    bac = _ouvrir(client)
    g = _active(client, bac["id"])
    assert g["nom"] == NOM and g["ouverte"] is False
    assert g["version"]["numero"] == 1 and g["version"]["etat"] == "publiee"
    assert g["version"]["porte_sur"] == ["mots"]
    plan = ok(client.get(f"/api/grilles/{g['id']}/versions/1", headers=LEA))
    attendu = grille_import.lire(flux(MODELE), flux(MODELE_LISTES), porte_sur="mots")["contenu"]
    assert plan["grille"]["nom"] == NOM
    assert len(_sql("SELECT 1 FROM grille_entree e JOIN grille_version v ON v.id = e.version_id "
                    "WHERE v.grille_id = ?", (g["id"],))) == len(attendu["entrees"]) > 5
    ligne = _sql("SELECT projet_id, cree_par FROM grille WHERE id = ?", (g["id"],))[0]
    assert ligne == {"projet_id": bac["id"], "cree_par": None}, "elle n'est à personne"


def test_chaque_bac_a_sable_a_la_sienne(client, jeu):
    un, deux = _active(client, _ouvrir(client)["id"]), _active(
        client, _ouvrir(client, SAM)["id"], SAM)
    assert un["id"] != deux["id"] and un["nom"] == deux["nom"]
    assert _sql("SELECT COUNT(DISTINCT version_id) AS n FROM projet_grille")[0]["n"] == 2


def test_recliquer_n_en_ajoute_pas(client, jeu):
    bac = _ouvrir(client)
    avant = _comptes()
    assert ok(client.post("/api/bac-a-sable", headers=LEA), 200)["id"] == bac["id"]
    assert _comptes() == avant


def test_la_page_s_y_sert_sans_aucune_autre_action(client, jeu):
    """Le propriétaire et son invité posent un relevé sur une copie du jeu, des mots comme
    la surface, sans avoir rien importé, publié ni activé."""
    bac = _ouvrir(client)
    ok(client.put(f"/api/projets/{bac['id']}/membres", headers=LEA,
                  json={"genre": "utilisateur", "principal": "sam", "role": "membre"}))
    g = _active(client, bac["id"])
    pl, bulle = _bulle(client, bac)
    _poser(client, g, region_id=bulle, entree_cle="cri", mots=[0])
    assert _active(client, bac["id"], SAM)["id"] == g["id"], "l'invité lit la même"
    _poser(client, g, SAM, planche_id=pl, entree_cle="ambiance")
    lus = ok(client.get(f"/api/planches/{pl}/releves", headers=SAM))
    assert sorted(r["entree_cle"] for r in lus["releves"]) == ["ambiance", "cri"]


# --------------------------------------------------------------------------- #
# Finir : la remise à neuf, l'effacement
# --------------------------------------------------------------------------- #
def _travailler(client, bac):
    """De quoi remplir chacune des seize tables, ou presque : un relevé de mots à son doute
    et son fil, un relevé à qualificatifs, un de surface, une passe, une grille masquée."""
    g = _active(client, bac["id"])
    pl, bulle = _bulle(client, bac)
    r = _poser(client, g, region_id=bulle, entree_cle="cri", mots=[0])
    _poser(client, g, region_id=bulle, entree_cle="intensite", mots=[1],
           qualificatifs=["taille"])
    _poser(client, g, planche_id=pl, entree_cle="ambiance")
    d = ok(client.post(f"/api/releves/{r['id']}/doutes", headers=LEA, json={"texte": "Sûr ?"}),
           201)
    ok(client.post(f"/api/doutes/{d['id']}/messages", headers=LEA, json={"texte": "Oui."}), 201)
    ok(client.put(f"/api/regions/{bulle}/passes/{g['id']}", headers=LEA, json={}))
    ok(client.put(f"/api/collections/{bac['base']['id']}/grilles-masquees/{g['id']}",
                  headers=LEA))
    return g


def test_la_remise_a_neuf_rend_une_grille_neuve_sans_releve(client, jeu):
    bac = _ouvrir(client)
    ancienne = _travailler(client, bac)
    assert _comptes()["releve"] == 3
    neuf = ok(client.post("/api/bac-a-sable/remise-a-neuf", headers=LEA))
    g = _active(client, neuf["id"])
    assert neuf["id"] != bac["id"] and g["id"] != ancienne["id"] and g["nom"] == NOM
    apres = _comptes()
    for t in ("releve", "releve_mot", "releve_qualificatif", "doute", "doute_message", "passe",
              "collection_grille_masquee"):
        assert apres[t] == 0, t
    assert apres["grille"] == apres["projet_grille"] == apres["grille_version"] == 1
    assert _sql("SELECT 1 FROM grille_version WHERE grille_id = ?", (ancienne["id"],)) == []


def test_l_effacement_emporte_tout_sans_orphelin(client, jeu):
    """Les seize tables reviennent à zéro : aucune n'est oubliée, puisqu'elles se lisent
    dans `TABLES_DES_GRILLES`. Le témoin : le travail les a d'abord remplies."""
    bac = _ouvrir(client)
    _travailler(client, bac)
    pleines = _comptes()
    assert all(pleines[t] for t in database.TABLES_DES_GRILLES), pleines
    conn = database.get_connection()
    try:
        r = socle._effacer_bac_a_sable(conn, autorisation.TOTALE, bac["id"], motif="lundi")
    finally:
        conn.close()
    assert r["efface"] is True
    assert set(_comptes().values()) == {0}
    assert _sql("SELECT 1 FROM projet WHERE id = ?", (bac["id"],)) == []


def test_l_effacement_ne_touche_pas_la_grille_d_un_autre_bac(client, jeu):
    bac, autre = _ouvrir(client), _ouvrir(client, SAM)
    g = _active(client, autre["id"], SAM)
    conn = database.get_connection()
    try:
        socle._effacer_bac_a_sable(conn, autorisation.TOTALE, bac["id"], motif="lundi")
    finally:
        conn.close()
    assert _active(client, autre["id"], SAM)["id"] == g["id"]


# --------------------------------------------------------------------------- #
# Le fichier absent ou refusé : le bac à sable naît, sans grille, et le serveur le dit
# --------------------------------------------------------------------------- #
def _sans_grille(client, caplog):
    """Le bac à sable est né entier, sans la moindre ligne de grille ni acte sous `grille`,
    et le journal du serveur le dit en ERREUR : rend sa ligne."""
    with caplog.at_level(logging.ERROR, logger="bd_annotator"):
        bac = _ouvrir(client)
    assert bac["base"] and len(bac["jeu"]) == 2, "tout le reste du bac à sable est là"
    assert ok(client.get(f"/api/projets/{bac['id']}/grilles", headers=LEA))["actives"] == []
    assert set(_comptes().values()) == {0}
    assert _sql("SELECT 1 FROM evenement WHERE cible_table = 'grille'") == []
    dits = [r.getMessage() for r in caplog.records
            if r.name == "bd_annotator" and r.levelno == logging.ERROR]
    assert len(dits) == 1 and "SANS grille" in dits[0], dits
    return dits[0]


def test_fichier_absent(client, jeu, caplog, monkeypatch, tmp_path):
    monkeypatch.setattr(socle, "GRILLE_DU_BAC", tmp_path / "parti.csv")
    assert "parti.csv" in _sans_grille(client, caplog)


def test_listes_absentes(client, jeu, caplog, monkeypatch, tmp_path):
    monkeypatch.setattr(socle, "GRILLE_DU_BAC_LISTES", tmp_path / "parties.csv")
    assert "parties.csv" in _sans_grille(client, caplog)


def test_fichier_refuse_ses_anomalies_dites(client, jeu, caplog, monkeypatch, tmp_path):
    f = tmp_path / "faux.csv"
    f.write_text("cle;forme;libelle\r\nzz;nimporte;Une entrée\r\n", encoding="utf-8")
    monkeypatch.setattr(socle, "GRILLE_DU_BAC", f)
    assert "nimporte" in _sans_grille(client, caplog)


def test_entete_invalide(client, jeu, caplog, monkeypatch, tmp_path):
    f = tmp_path / "faux.csv"
    f.write_text("a;b\r\n1;2\r\n", encoding="utf-8")
    monkeypatch.setattr(socle, "GRILLE_DU_BAC", f)
    assert "colonnes obligatoires" in _sans_grille(client, caplog)


def test_fichier_mal_encode(client, jeu, caplog, monkeypatch, tmp_path):
    f = tmp_path / "faux.csv"
    f.write_bytes("cle;forme;libelle\r\nécho;simple;x\r\n".encode("latin-1"))
    monkeypatch.setattr(socle, "GRILLE_DU_BAC", f)
    _sans_grille(client, caplog)


def test_cellule_que_le_lecteur_csv_refuse(client, jeu, caplog, monkeypatch, tmp_path):
    """Au-delà de sa limite de champ, `csv` lève sa propre erreur : ni `OSError`, ni
    `ValueError`, et le fichier n'en est pas moins refusé."""
    f = tmp_path / "faux.csv"
    f.write_text("cle;forme;libelle\r\nzz;simple;" + "x" * 200_000 + "\r\n", encoding="utf-8")
    monkeypatch.setattr(socle, "GRILLE_DU_BAC", f)
    _sans_grille(client, caplog)


def test_un_refus_apres_l_ecriture_ne_laisse_rien(client, jeu, caplog, monkeypatch):
    """Importée et publiée, refusée à l'activation : la grille déjà écrite est défaite, ses
    actes au journal aussi. Sans le point de sauvegarde, le bac à sable garderait un
    brouillon que personne n'a demandé ; sans sa levée, la transaction de la naissance."""
    def refuser(*_a, **_k):
        raise grille_import.Refus(409, "refus d'essai")
    monkeypatch.setattr(grille_import, "activer", refuser)
    _sans_grille(client, caplog)


def test_une_panne_de_la_base_n_est_pas_celle_du_fichier(client, jeu, monkeypatch):
    """Elle remonte : aucun bac à sable à moitié né, et rien qui se fasse passer pour un
    fichier refusé."""
    def panne(*_a, **_k):
        raise sqlite3.OperationalError("disk I/O error")
    monkeypatch.setattr(grille_import, "activer", panne)
    assert client.post("/api/bac-a-sable", headers=LEA).status_code == 500
    assert _sql("SELECT 1 FROM projet WHERE bac_a_sable_de = 'lea'") == []


# --------------------------------------------------------------------------- #
# L'isolement
# --------------------------------------------------------------------------- #
def test_personne_d_autre_ne_la_lit(client, jeu):
    """Ni un compte quelconque, ni un administrateur (sa portée est bornée aux bacs à sable
    des autres), ni le propriétaire d'un autre bac à sable, dont la grille porte le même
    nom : le 404 d'un identifiant qui n'existe pas."""
    bac = _ouvrir(client)
    _ouvrir(client, SAM)
    g = _active(client, bac["id"])
    for qui in (RITA, HUGO, SAM):
        for chemin in (f"/api/grilles/{g['id']}", f"/api/grilles/{g['id']}/versions/1",
                       f"/api/projets/{bac['id']}/grilles"):
            assert client.get(chemin, headers=qui).status_code == 404, (qui, chemin)


def test_un_autre_compte_n_y_ecrit_pas(client, jeu):
    bac = _ouvrir(client)
    g = _active(client, bac["id"])
    pl, bulle = _bulle(client, bac)
    for qui in (RITA, HUGO):
        r = client.post("/api/releves", headers=qui, json={
            "grille_id": g["id"], "version": 1, "region_id": bulle, "entree_cle": "cri",
            "mots": [0]})
        assert r.status_code == 404, (qui, r.text)
        assert client.post(f"/api/grilles/{g['id']}/versions/1/publication",
                           headers=qui).status_code == 404


def _outil(db_path, outil, *args):
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(db_path.parent)}
    c = sqlite3.connect(db_path)
    try:
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        c.close()
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / outil), *args],
                       cwd=str(REPO_ROOT), env=env, capture_output=True)
    return r.returncode, r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")


def test_rien_d_elle_ne_sort(client, jeu, db_path):
    """L'export de la copie du jeu, le seul permis depuis un bac à sable, et les outils de
    sortie, avec un relevé posé : ni son nom, ni une clé de relevé, ni une entrée."""
    bac = _ouvrir(client)
    g = _active(client, bac["id"])
    _pl, bulle = _bulle(client, bac)
    _poser(client, g, region_id=bulle, entree_cle="origine-du-son", mots=[0],
           qualificatifs=["personnage"], precision="ZZPRECIS8")
    assert "ZZPRECIS8" in client.get(f"/api/planches/{_pl}/releves", headers=LEA).text
    copie = next(j for j in bac["jeu"] if j["role"] == "exemple")
    sorties = {}
    for chemin in (f"/api/export/json?album_id={copie['album_id']}",
                   f"/api/export/csv?album_id={copie['album_id']}",
                   f"/api/export/tei?album_id={copie['album_id']}"):
        r = client.get(chemin, headers=LEA)
        assert r.status_code == 200, (chemin, r.text[:300])
        sorties[chemin] = r.text
    for outil in ("description_collection.py", "metadonnees_collection.py"):
        code, texte = _outil(db_path, outil, "--json", "-")
        assert code == 0, texte[-600:]
        sorties[outil] = texte
    for surface, texte in sorties.items():
        assert len(texte) > 40, surface
        for interdit in (NOM, "ZZPRECIS8", "grille_id", "entree_cle"):
            assert interdit not in texte, f"{surface} laisse sortir « {interdit} »"


# --------------------------------------------------------------------------- #
# Le journal
# --------------------------------------------------------------------------- #
def test_ses_actes_s_ecrivent_sous_grille_et_ne_comptent_pour_personne(client, jeu):
    bac = _ouvrir(client)
    g = _active(client, bac["id"])
    actes = _sql("SELECT type, agent FROM evenement WHERE cible_table = 'grille' "
                 "AND cible_id = ? ORDER BY id", (g["id"],))
    assert [a["type"] for a in actes] == ["creation", "modification", "modification", "lien"]
    conn = database.get_connection()
    try:
        assert "lea" not in comptes.traces(conn)[0]
    finally:
        conn.close()
    ok(client.post("/api/bac-a-sable/remise-a-neuf", headers=LEA))
    conn = database.get_connection()
    try:
        assert "lea" not in comptes.traces(conn)[0], "ni une fois l'ancien bac à sable parti"
        # Ses actes sous `grille`, seuls, ne donnent aucun rang (le reste de la naissance
        # d'un bac à sable, qui en donne un depuis COL-4, n'est pas la question ici).
        conn.execute("DELETE FROM evenement WHERE cible_table <> 'grille'")
        conn.commit()
        assert _sql("SELECT COUNT(*) AS n FROM evenement WHERE agent = 'lea'")[0]["n"] >= 8
        assert "lea" not in _commun.pseudonymes(conn)
    finally:
        conn.close()


def test_publier_par_la_route_garde_son_auteur(client, jeu):
    """Le cœur de la publication (`grille_import.publier`) est partagé : la grille de la
    naissance n'est à personne, celle qu'une personne publie reste signée en base."""
    bac = _ouvrir(client)
    gid = importer(client, bac["id"], LEA, nom="Mienne")["grille_id"]
    ok(client.post(f"/api/grilles/{gid}/versions/1/publication", headers=LEA))
    naissance = _active(client, bac["id"])["id"]
    assert [r["publiee_par"] for r in _sql(
        "SELECT publiee_par FROM grille_version WHERE grille_id IN (?, ?) ORDER BY grille_id",
        (naissance, gid))] == [None, "lea"]


def test_la_portee_de_lea_ne_gagne_rien_ailleurs(client, jeu):
    """La grille est active sur SON projet : aucune question transverse n'en dépend."""
    _ouvrir(client)
    moi = ok(client.get("/api/moi", headers=LEA))
    assert moi["acces"]["total"] is False
    assert client.get("/api/fonds/notices", headers=LEA).status_code == 403


# --------------------------------------------------------------------------- #
# L'image
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("chemin", [config.GRILLE_DU_BAC, config.GRILLE_DU_BAC_LISTES])
def test_le_fichier_est_dans_le_depot(chemin):
    """Dans l'image, le même test dit que `COPY . .` l'y a mis (étape `test`, même contexte
    et même `.dockerignore` que `runtime`)."""
    assert chemin.is_file()
    assert chemin.resolve().is_relative_to(config.BASE_DIR)


def test_l_image_copie_le_fichier():
    """Le manque ne se verrait qu'en production. `.dockerignore` n'exclut pas ces fichiers,
    et `runtime`, l'étape livrée, copie le code entier."""
    dockerfile = REPO_ROOT / "deploy" / "Dockerfile"
    ignore = REPO_ROOT / ".dockerignore"
    if not ignore.is_file() or not dockerfile.is_file():
        pytest.skip("hors du contexte de construction")
    motifs = [ligne.strip().rstrip("/") for ligne in ignore.read_text("utf-8").splitlines()
              if ligne.strip() and not ligne.startswith(("#", "!"))]
    for fichier in (config.GRILLE_DU_BAC, config.GRILLE_DU_BAC_LISTES):
        rel = fichier.relative_to(config.BASE_DIR).as_posix()
        for motif in motifs:
            assert not fnmatch.fnmatch(rel, motif), (rel, motif)
            assert not any(fnmatch.fnmatch(p, motif) for p in rel.split("/")[:-1]), (rel, motif)
    runtime = dockerfile.read_text("utf-8").split("AS runtime", 1)[1]
    assert "COPY . ." in runtime
