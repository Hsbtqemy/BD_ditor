"""Import en lot du vocabulaire analytique (`tools/importer_vocabulaire.py`, piste B).

Vérifie le chargement d'un tableur CSV point-virgule vers le palier domaine → dimension →
valeur + couche lexique SKOS : création, IDEMPOTENCE (rejouable sans doublon), doctrine
« pré-remplir sans écraser » (une glose humaine n'est jamais remplacée ; un champ vide se
remplit), portée `collection_id` posée à la création, dimension hors domaine, validation
(cible/dimension), et le bout-en-bout CLI sur la template livrée (garde UTF-8 Windows).
"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO_ROOT))

import database  # noqa: E402
import importer_vocabulaire as iv  # noqa: E402
from conftest import direct_query  # noqa: E402

MODELE = TOOLS / "vocabulaire-modele.csv"

# Un petit tableur autonome (deux domaines, dont un traversant personnage ET case).
CSV_MINI = (
    "domaine;domaine_definition;cible;dimension;dimension_definition;dimension_note_portee;valeur;valeur_definition\n"
    "émotions;Charge affective;case;valence;Polarité de la scène;;positive;Affect plaisant\n"
    "émotions;;case;valence;;;négative;\n"
    "représentation;Groupes et minorités;personnage;genre;Genre représenté;genre perçu, non l'identité;femme;\n"
    "représentation;;case;scène stéréotypée;La case rejoue-t-elle un stéréotype ?;;oui;\n"
)


# --------------------------------------------------------------------------- #
# Aides
# --------------------------------------------------------------------------- #
def _ecrire(tmp_path, contenu, nom="voc.csv"):
    p = tmp_path / nom
    p.write_text(contenu, encoding="utf-8")
    return p


def _charger(fichier, collection_id=None):
    """Charge un tableur EN PROCESS (base patchée par la fixture data_dir). Renvoie
    (résumé, avertissements, anomalies)."""
    lignes, anomalies = iv.lire_csv(str(fichier))
    conn = database.get_connection()
    try:
        res, avert = iv.importer(conn, lignes, collection_id)
        conn.commit()
    finally:
        conn.close()
    return res, avert, anomalies


def _creer_collection(nom="Étude test"):
    conn = database.get_connection()
    try:
        cur = conn.execute("INSERT INTO collection (nom) VALUES (?)", (nom,))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _run(db_path, data_dir, *args):
    """Invoque l'outil en SOUS-PROCESSUS (décodage UTF-8 sans PYTHONUTF8 → exerce le garde
    de portabilité Windows de _commun.forcer_utf8)."""
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(data_dir)}
    return subprocess.run([sys.executable, str(TOOLS / "importer_vocabulaire.py"), *args],
                          cwd=str(REPO_ROOT), env=env, capture_output=True,
                          text=True, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Création
# --------------------------------------------------------------------------- #
def test_cree_le_palier_complet(tmp_path, data_dir, db_path):
    res, avert, anomalies = _charger(_ecrire(tmp_path, CSV_MINI))
    assert not anomalies and not avert
    assert res["domaines"]["cree"] == 2
    assert res["dimensions"]["cree"] == 3        # valence, genre, scène stéréotypée
    assert res["valeurs"]["cree"] == 4

    # domaine documenté, dimension rattachée, valeur glosée
    dom = direct_query(db_path, "SELECT * FROM domaine WHERE nom = 'émotions'")[0]
    assert dom["definition"] == "Charge affective" and dom["etat"] == "provisoire"
    dim = direct_query(db_path,
                       "SELECT d.*, dom.nom AS domaine FROM attribut_dimension d "
                       "JOIN domaine dom ON dom.id = d.domaine_id "
                       "WHERE d.cible = 'case' AND d.nom = 'valence'")[0]
    assert dim["domaine"] == "émotions" and dim["definition"] == "Polarité de la scène"
    val = direct_query(db_path, "SELECT * FROM attribut_valeur WHERE valeur = 'positive'")[0]
    assert val["definition"] == "Affect plaisant"


def test_dimension_note_portee_va_sur_la_dimension(tmp_path, data_dir, db_path):
    _charger(_ecrire(tmp_path, CSV_MINI))
    dim = direct_query(db_path,
                       "SELECT * FROM attribut_dimension WHERE cible='personnage' AND nom='genre'")[0]
    assert dim["note_portee"] == "genre perçu, non l'identité"


def test_domaine_traverse_les_cibles(tmp_path, data_dir, db_path):
    """« représentation » regroupe une dimension personnage ET une dimension case."""
    _charger(_ecrire(tmp_path, CSV_MINI))
    cibles = {r["cible"] for r in direct_query(
        db_path, "SELECT d.cible FROM attribut_dimension d "
                 "JOIN domaine dom ON dom.id = d.domaine_id WHERE dom.nom = 'représentation'")}
    assert cibles == {"personnage", "case"}


# --------------------------------------------------------------------------- #
# Idempotence & « pré-remplir sans écraser »
# --------------------------------------------------------------------------- #
def test_idempotent(tmp_path, data_dir, db_path):
    fichier = _ecrire(tmp_path, CSV_MINI)
    _charger(fichier)
    res, _, _ = _charger(fichier)                 # rejoué
    assert res["domaines"] == {"cree": 0, "existant": 2}
    assert res["dimensions"] == {"cree": 0, "existant": 3}
    assert res["valeurs"] == {"cree": 0, "existant": 4}
    # aucun doublon
    assert direct_query(db_path, "SELECT COUNT(*) c FROM domaine")[0]["c"] == 2
    assert direct_query(db_path, "SELECT COUNT(*) c FROM attribut_valeur")[0]["c"] == 4


def test_ne_remplace_jamais_une_glose_humaine(tmp_path, data_dir, db_path):
    conn = database.get_connection()
    conn.execute("INSERT INTO domaine (nom, definition, note_portee) VALUES "
                 "('émotions', 'glose humaine', 'portée humaine')")
    conn.commit(); conn.close()

    _charger(_ecrire(tmp_path, CSV_MINI))         # le CSV propose une AUTRE définition
    dom = direct_query(db_path, "SELECT * FROM domaine WHERE nom='émotions'")[0]
    assert dom["definition"] == "glose humaine"   # inchangée
    assert dom["note_portee"] == "portée humaine"


def test_remplit_un_champ_vide(tmp_path, data_dir, db_path):
    conn = database.get_connection()               # terme créé ÉMERGENT, sans définition
    conn.execute("INSERT INTO domaine (nom) VALUES ('émotions')")
    conn.commit(); conn.close()

    _charger(_ecrire(tmp_path, CSV_MINI))
    dom = direct_query(db_path, "SELECT * FROM domaine WHERE nom='émotions'")[0]
    assert dom["definition"] == "Charge affective"   # champ vide → rempli


def test_rattache_une_dimension_orpheline(tmp_path, data_dir, db_path):
    """Une dimension créée hors domaine (émergent) est rattachée si le CSV la place dans un
    domaine — mais un rattachement existant n'est jamais changé."""
    conn = database.get_connection()
    conn.execute("INSERT INTO attribut_dimension (cible, nom) VALUES ('case', 'valence')")
    conn.commit(); conn.close()

    _charger(_ecrire(tmp_path, CSV_MINI))
    dim = direct_query(db_path,
                       "SELECT dom.nom AS domaine FROM attribut_dimension d "
                       "JOIN domaine dom ON dom.id = d.domaine_id "
                       "WHERE d.cible='case' AND d.nom='valence'")[0]
    assert dim["domaine"] == "émotions"


# --------------------------------------------------------------------------- #
# Portée (collection)
# --------------------------------------------------------------------------- #
def test_portee_globale_par_defaut(tmp_path, data_dir, db_path):
    _charger(_ecrire(tmp_path, CSV_MINI))
    portees = {r["collection_id"] for r in direct_query(db_path, "SELECT collection_id FROM domaine")}
    assert portees == {None}                       # NULL = global


def test_portee_locale_a_une_collection(tmp_path, data_dir, db_path):
    cid = _creer_collection()
    _charger(_ecrire(tmp_path, CSV_MINI), collection_id=cid)
    for table in ("domaine", "attribut_dimension", "attribut_valeur"):
        portees = {r["collection_id"] for r in direct_query(db_path, f"SELECT collection_id FROM {table}")}
        assert portees == {cid}, table


def test_portee_non_reassignee_sur_terme_existant(tmp_path, data_dir, db_path):
    """La portée ne se pose qu'à la CRÉATION : réimporter dans une collection ne déplace
    pas un terme déjà global (décision d'appartenance = humaine)."""
    cid = _creer_collection()
    fichier = _ecrire(tmp_path, CSV_MINI)
    _charger(fichier)                              # d'abord global
    _charger(fichier, collection_id=cid)           # rejoué avec portée
    dom = direct_query(db_path, "SELECT collection_id FROM domaine WHERE nom='émotions'")[0]
    assert dom["collection_id"] is None            # reste global


# --------------------------------------------------------------------------- #
# Hors domaine, valeur absente, validation, divergences
# --------------------------------------------------------------------------- #
def test_dimension_hors_domaine(tmp_path, data_dir, db_path):
    csv = ("domaine;domaine_definition;cible;dimension;dimension_definition;dimension_note_portee;valeur;valeur_definition\n"
           ";;case;cadrage;Échelle de plan;;gros plan;\n")
    res, _, anomalies = _charger(_ecrire(tmp_path, csv))
    assert not anomalies and res["domaines"]["cree"] == 0 and res["dimensions"]["cree"] == 1
    dim = direct_query(db_path, "SELECT * FROM attribut_dimension WHERE nom='cadrage'")[0]
    assert dim["domaine_id"] is None


def test_valeur_vide_declare_la_dimension_seule(tmp_path, data_dir, db_path):
    csv = ("domaine;domaine_definition;cible;dimension;dimension_definition;dimension_note_portee;valeur;valeur_definition\n"
           "style;Choix graphiques;case;cadrage;Échelle de plan;;;\n")
    res, _, _ = _charger(_ecrire(tmp_path, csv))
    assert res["dimensions"]["cree"] == 1 and res["valeurs"]["cree"] == 0
    assert direct_query(db_path, "SELECT COUNT(*) c FROM attribut_valeur")[0]["c"] == 0


def test_cible_invalide_et_dimension_vide_ignorees(tmp_path, data_dir, db_path):
    csv = ("domaine;domaine_definition;cible;dimension;dimension_definition;dimension_note_portee;valeur;valeur_definition\n"
           "émotions;;planche;valence;;;positive;\n"      # cible inconnue → ignorée
           "émotions;;case;;;;orpheline;\n"               # dimension vide → ignorée
           "émotions;Charge;case;valence;;;positive;\n")  # valide
    res, _, anomalies = _charger(_ecrire(tmp_path, csv))
    assert len(anomalies) == 2
    assert res["dimensions"]["cree"] == 1 and res["valeurs"]["cree"] == 1


def test_avertit_sur_definitions_divergentes(tmp_path, data_dir, db_path):
    csv = ("domaine;domaine_definition;cible;dimension;dimension_definition;dimension_note_portee;valeur;valeur_definition\n"
           "émotions;Charge affective;case;valence;;;positive;\n"
           "émotions;AUTRE définition;case;valence;;;négative;\n")   # domaine redéfini
    res, avert, _ = _charger(_ecrire(tmp_path, csv))
    assert any("domaine" in a and "divergentes" in a for a in avert)
    dom = direct_query(db_path, "SELECT definition FROM domaine WHERE nom='émotions'")[0]
    assert dom["definition"] == "Charge affective"    # la première fait foi


# --------------------------------------------------------------------------- #
# CLI (bout en bout)
# --------------------------------------------------------------------------- #
def test_cli_charge_la_template_livree(data_dir, db_path):
    """La template committée est un CSV valide et s'importe de bout en bout (garde UTF-8)."""
    r = _run(db_path, data_dir, str(MODELE))
    assert r.returncode == 0, r.stderr
    assert direct_query(db_path, "SELECT COUNT(*) c FROM domaine")[0]["c"] == 3
    assert direct_query(db_path, "SELECT COUNT(*) c FROM attribut_dimension")[0]["c"] == 8
    assert direct_query(db_path, "SELECT COUNT(*) c FROM attribut_valeur")[0]["c"] == 21


def test_cli_dry_run_n_ecrit_rien(tmp_path, data_dir, db_path):
    fichier = _ecrire(tmp_path, CSV_MINI)
    r = _run(db_path, data_dir, str(fichier), "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "APERÇU" in r.stderr
    assert direct_query(db_path, "SELECT COUNT(*) c FROM domaine")[0]["c"] == 0


def test_cli_collection_introuvable(tmp_path, data_dir, db_path):
    fichier = _ecrire(tmp_path, CSV_MINI)
    r = _run(db_path, data_dir, str(fichier), "--collection", "9999")
    assert r.returncode != 0
    assert "introuvable" in r.stderr
    assert direct_query(db_path, "SELECT COUNT(*) c FROM domaine")[0]["c"] == 0


def test_cli_entete_invalide(tmp_path, data_dir, db_path):
    fichier = _ecrire(tmp_path, "domaine;valeur\némotions;positive\n")
    r = _run(db_path, data_dir, str(fichier))
    assert r.returncode != 0
    assert "En-tête invalide" in r.stderr


# --------------------------------------------------------------------------- #
# Route API (bouton « Importer » du panneau Lexique) — même cœur partagé
# --------------------------------------------------------------------------- #
def _poster(client, contenu, collection_id=None):
    data = {"collection_id": str(collection_id)} if collection_id is not None else {}
    return client.post("/api/lexique/importer",
                       files={"file": ("voc.csv", contenu, "text/csv")}, data=data)


def test_api_importe(client, db_path):
    r = _poster(client, CSV_MINI)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["resume"]["domaines"]["cree"] == 2 and body["lignes"] == 4
    assert not body["anomalies"] and not body["avertissements"]
    assert direct_query(db_path, "SELECT COUNT(*) c FROM attribut_valeur")[0]["c"] == 4
    # le read model reflète l'import
    lex = client.get("/api/lexique").json()
    assert {d["nom"] for d in lex["domaines"]} == {"émotions", "représentation"}


def test_api_idempotent(client, db_path):
    _poster(client, CSV_MINI)
    body = _poster(client, CSV_MINI).json()
    assert body["resume"]["domaines"] == {"cree": 0, "existant": 2}
    assert direct_query(db_path, "SELECT COUNT(*) c FROM domaine")[0]["c"] == 2


def test_api_portee_collection(client, db_path):
    cid = _creer_collection()
    _poster(client, CSV_MINI, collection_id=cid)
    portees = {r["collection_id"] for r in direct_query(db_path, "SELECT collection_id FROM domaine")}
    assert portees == {cid}


def test_api_collection_introuvable(client, db_path):
    r = _poster(client, CSV_MINI, collection_id=9999)
    assert r.status_code == 404
    assert direct_query(db_path, "SELECT COUNT(*) c FROM domaine")[0]["c"] == 0


def test_api_entete_invalide(client, db_path):
    r = _poster(client, "domaine;valeur\némotions;positive\n")
    assert r.status_code == 400 and "En-tête invalide" in r.json()["detail"]


def test_api_fichier_vide(client):
    r = _poster(client, "")
    assert r.status_code == 400
