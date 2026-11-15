"""Une grille DÉRIVÉE dit d'où elle vient (ANN-7, « Le catalogue et le partage » ; voulu par
Hugo le 2026-11-15, v40).

Dériver une grille, c'est tirer le classeur d'une version et le réimporter comme grille NEUVE
d'un autre projet ; les `cle` héritées gardent les deux comparables. Ce qui manquait était la
trace de l'origine, que `grille.id`, propre à l'instance, ne pouvait pas dire. Depuis la v40 :

- toute grille naît avec un IDENTIFIANT neuf (un UUID), qui survit à l'instance ;
- son classeur le porte, avec son nom et le numéro de la version tirée, en bas de la feuille
  « 1. La grille » ;
- une grille NEUVE importée d'un classeur tiré d'une AUTRE grille se lit « dérivée de
  « <nom> », v<N> » — dans le plan, dans la fiche du projet, dans le bilan de l'import ;
- une version SUIVANTE n'écrit rien : l'origine s'écrit à la naissance ;
- l'identifiant d'un classeur n'est JAMAIS recopié comme identifiant de la neuve ;
- deux CSV ne portent rien, et un classeur rempli à la main sans ces lignes reste valide.

La grille est FICTIVE (`tools/grille-modele.csv`), comme dans `test_grilles`.
"""
import io
import os
import sqlite3
import subprocess
import sys
import uuid
import zipfile

import openpyxl
import pytest

import grille_tableur
import grilles
from grilles_decor import LEA, ZOE, importer, monter, ok

pytestmark = pytest.mark.usefixtures("sans_grille_de_travail")

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def decor(client, db_path, derriere_proxy):
    return monter(client, db_path)


def _q(db_path, sql, p=()):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, p)]
    finally:
        c.close()


def _ligne(db_path, gid):
    return _q(db_path, "SELECT * FROM grille WHERE id = ?", (gid,))[0]


def _classeur(client, gid, numero=1, qui=LEA) -> bytes:
    r = client.get(f"/api/grilles/{gid}/versions/{numero}/tableur", headers=qui)
    assert r.status_code == 200, r.text[:300]
    return r.content


def _importer(client, projet_id, qui, data: bytes, attendu=(200,), **champs):
    r = client.post(f"/api/projets/{projet_id}/grilles/import", headers=qui,
                    files={"fichier": ("grille.xlsx", data, XLSX)},
                    data={k: str(v) for k, v in champs.items()})
    assert r.status_code in attendu, (r.status_code, r.text[:800])
    return r.json()


def _feuille_grille(data: bytes) -> dict:
    """Les lignes de « 1. La grille » : {libellé de la colonne A: valeur de la colonne B}."""
    wb = openpyxl.load_workbook(io.BytesIO(data))
    return {ws_a.value: ws_b.value for ws_a, ws_b, *_ in
            wb[grille_tableur.FEUILLE_GRILLE].iter_rows(min_col=1, max_col=3)
            if ws_a.value}


def _retouche(data: bytes, retouche, feuille=grille_tableur.FEUILLE_GRILLE) -> bytes:
    wb = openpyxl.load_workbook(io.BytesIO(data))
    retouche(wb[feuille])
    sortie = io.BytesIO()
    wb.save(sortie)
    return sortie.getvalue()


def _poser_valeur(titre, valeur):
    """Une retouche : la cellule B de la ligne dont la colonne A dit `titre`."""
    def retouche(ws):
        for a, b, *_ in ws.iter_rows(min_col=1, max_col=3):
            if a.value == titre:
                b.value = valeur
                return
        raise AssertionError(f"pas de ligne « {titre} »")
    return retouche


def _une_definition_retouchee(ws):
    """Une retouche du CONTENU : la définition de la première entrée qui en a une."""
    titres = [c.value for c in ws[1]]
    col = titres.index(grille_tableur.TITRES["definition"])
    for ligne in ws.iter_rows(min_row=2):
        if ligne[col].value:
            ligne[col].value = f"{ligne[col].value} (retouchée)"
            return
    raise AssertionError("aucune définition à retoucher")


def _origine_dite(res) -> list:
    return [a["code"] for a in res["a_savoir"] if a["code"].startswith("origine")]


def _sans_origine(ws):
    """Le classeur rempli à la main : sans les lignes de l'origine."""
    titres = {grille_tableur.TITRE_ORIGINE, *grille_tableur.TITRES_GRILLE.values()} - {
        t for _, t, _ in grille_tableur.CHAMPS_GRILLE}
    for a, b, c in ws.iter_rows(min_col=1, max_col=3):
        if a.value in titres:
            a.value = b.value = c.value = None


def _grille_publiee(client, projet_id, qui=LEA, nom="Signaux"):
    gid = importer(client, projet_id, qui, nom=nom)["grille_id"]
    ok(client.post(f"/api/grilles/{gid}/versions/1/publication", headers=qui))
    return gid


# --------------------------------------------------------------------------- #
# Le test de la case : tirer, réimporter ailleurs, lire l'origine
# --------------------------------------------------------------------------- #
def test_le_classeur_tire_d_une_grille_et_reimporte_ailleurs_dit_d_ou_elle_vient(
        client, decor, db_path):
    source = _grille_publiee(client, decor["p"])
    data = _classeur(client, source)
    res = _importer(client, decor["q"], ZOE, data, nom="Signaux de Q")
    assert res["ecrit"] and res["derivee_de"] == {"nom": "Signaux", "version": 1}
    gid = res["grille_id"]
    # Le plan de la grille le dit…
    plan = ok(client.get(f"/api/grilles/{gid}/versions/1", headers=ZOE))
    assert plan["grille"]["derivee_de"] == {"nom": "Signaux", "version": 1}
    # … et ce que lit le bloc Grilles de la fiche de son projet.
    vue = next(g for g in ok(client.get(f"/api/projets/{decor['q']}/grilles",
                                        headers=ZOE))["grilles"] if g["id"] == gid)
    assert vue["derivee_de"] == {"nom": "Signaux", "version": 1}
    # La source, elle, ne vient de rien.
    assert ok(client.get(f"/api/grilles/{source}/versions/1", headers=LEA))["grille"][
        "derivee_de"] is None
    # L'identifiant de la source n'est pas recopié : la neuve a le sien, et la ligne garde
    # celui de la source comme son origine.
    s, d = _ligne(db_path, source), _ligne(db_path, gid)
    assert grilles.identifiant_lu(d["identifiant"]) == d["identifiant"]
    assert d["identifiant"] != s["identifiant"]
    assert (d["derivee_de_identifiant"], d["derivee_de_nom"], d["derivee_de_version"]) == (
        s["identifiant"], "Signaux", 1)
    # Le journal garde l'origine dans l'acte de naissance.
    assert _q(db_path, "SELECT COUNT(*) AS n FROM evenement WHERE cible_table = 'grille' "
                       "AND cible_id = ? AND type = 'creation' "
                       "AND json_extract(apres, '$.derivee_de.identifiant') = ?",
              (gid, s["identifiant"]))[0]["n"] == 1


def test_le_classeur_porte_l_identifiant_le_nom_et_la_version_tiree(client, decor, db_path):
    gid = _grille_publiee(client, decor["p"])
    # Une version 2 : le classeur dit la version TIRÉE, pas la dernière.
    ok(client.post(f"/api/grilles/{gid}/rubriques", headers=LEA,
                   json={"libelle": "Ajoutée"}), 201)
    for numero in (1, 2):
        lignes = _feuille_grille(_classeur(client, gid, numero))
        assert lignes["Tiré de la grille"] == "Signaux"
        assert lignes["Version tirée"] == str(numero)
        assert lignes["Identifiant de la grille"] == _ligne(db_path, gid)["identifiant"]
    lu = grille_tableur.lire_classeur(_classeur(client, gid, 2))["grille"]
    assert lu["origine_version"][0] == "2" and lu["origine_nom"][0] == "Signaux"


def test_l_origine_ne_change_pas_l_empreinte_du_classeur(client, decor):
    """Relu tel quel, le classeur rend la même version : « aucun changement »."""
    gid = _grille_publiee(client, decor["p"])
    res = _importer(client, decor["p"], LEA, _classeur(client, gid), grille_id=gid)
    assert res["aucun_changement"]


# --------------------------------------------------------------------------- #
# Les gardes : la version suivante n'écrit rien ; l'identifiant n'est jamais recopié
# --------------------------------------------------------------------------- #
def test_une_version_suivante_tiree_d_elle_meme_n_ecrit_rien_et_se_tait(client, decor,
                                                                       db_path):
    gid = _grille_publiee(client, decor["p"])
    avant = _ligne(db_path, gid)
    data = _retouche(_classeur(client, gid), _une_definition_retouchee,
                     feuille=grille_tableur.FEUILLE_ENTREES)
    res = _importer(client, decor["p"], LEA, data, grille_id=gid)
    assert res["ecrit"] and res["version"]["numero"] == 2 and res["derivee_de"] is None
    assert _origine_dite(res) == []
    assert _ligne(db_path, gid) == avant


def test_une_version_suivante_tiree_d_une_autre_n_ecrit_rien_et_le_dit(client, decor,
                                                                      db_path):
    autre = _grille_publiee(client, decor["q"], ZOE, nom="Autre")
    cible = _grille_publiee(client, decor["p"])
    avant = _ligne(db_path, cible)
    data = _classeur(client, autre, qui=ZOE)
    res = _importer(client, decor["p"], LEA, data, grille_id=cible, a_blanc="true")
    assert res["derivee_de"] is None
    note = [a for a in res["a_savoir"] if a["code"] == "origine_ignoree"]
    assert len(note) == 1 and "« Autre »" in note[0]["probleme"]
    assert note[0]["question"] == "Identifiant de la grille"
    _importer(client, decor["p"], LEA, data, grille_id=cible)
    assert _ligne(db_path, cible) == avant


def test_l_identifiant_d_un_classeur_n_est_jamais_celui_de_la_neuve(client, decor, db_path):
    """Réimporté deux fois dans deux projets, puis dans le sien sous un autre nom : trois
    grilles neuves, trois identifiants à elles, toutes dérivées de la même."""
    source = _grille_publiee(client, decor["p"])
    data = _classeur(client, source)
    nees = [_importer(client, decor["q"], ZOE, data, nom="Q1")["grille_id"],
            _importer(client, decor["q"], ZOE, data, nom="Q2")["grille_id"],
            _importer(client, decor["p"], LEA, data, nom="Dans P")["grille_id"]]
    lignes = [_ligne(db_path, g) for g in [source, *nees]]
    assert len({l["identifiant"] for l in lignes}) == 4
    assert {l["derivee_de_identifiant"] for l in lignes[1:]} == {lignes[0]["identifiant"]}
    # Une dérivée de dérivée nomme sa source immédiate, pas la première.
    petite = _importer(client, decor["q"], ZOE, _classeur(client, nees[0], qui=ZOE),
                       nom="Petite-fille")
    assert petite["derivee_de"] == {"nom": "Q1", "version": 1}


# --------------------------------------------------------------------------- #
# Ce qui ne porte rien, ce qui porte mal
# --------------------------------------------------------------------------- #
def test_deux_csv_ne_portent_aucune_origine(client, decor, db_path):
    res = importer(client, decor["q"], ZOE, nom="Par CSV")
    assert res["derivee_de"] is None
    d = _ligne(db_path, res["grille_id"])
    assert d["derivee_de_identifiant"] is None and grilles.identifiant_lu(d["identifiant"])


def test_un_classeur_rempli_a_la_main_sans_ces_lignes_reste_valide(client, decor, db_path):
    gid = _grille_publiee(client, decor["p"])
    data = _retouche(_classeur(client, gid), _sans_origine)
    assert "Identifiant de la grille" not in _feuille_grille(data)
    res = _importer(client, decor["q"], ZOE, data, nom="À la main")
    assert res["ecrit"] and res["derivee_de"] is None and _origine_dite(res) == []
    assert _ligne(db_path, res["grille_id"])["derivee_de_identifiant"] is None


def test_un_classeur_d_une_autre_instance_dit_son_origine(client, decor, db_path):
    """L'identifiant survit à l'instance : un classeur venu d'ailleurs dit d'où il vient, même
    si aucune grille d'ici ne porte cet identifiant."""
    gid = _grille_publiee(client, decor["p"])
    ailleurs = str(uuid.uuid4())
    data = _retouche(_classeur(client, gid), _poser_valeur("Identifiant de la grille",
                                                           ailleurs.upper()))
    data = _retouche(data, _poser_valeur("Tiré de la grille", "La grille d'ailleurs"))
    data = _retouche(data, _poser_valeur("Version tirée", "v7"))
    res = _importer(client, decor["q"], ZOE, data, nom="Venue d'ailleurs")
    assert res["derivee_de"] == {"nom": "La grille d'ailleurs", "version": 7}
    d = _ligne(db_path, res["grille_id"])
    # Même inconnu ici, l'identifiant du classeur n'est pas recopié : la neuve a le sien.
    assert d["derivee_de_identifiant"] == ailleurs != d["identifiant"]


def test_un_identifiant_illisible_n_ecrit_rien_et_le_dit(client, decor, db_path):
    gid = _grille_publiee(client, decor["p"])
    data = _retouche(_classeur(client, gid), _poser_valeur("Identifiant de la grille",
                                                           "pas-un-identifiant"))
    res = _importer(client, decor["q"], ZOE, data, nom="Illisible")
    assert res["ecrit"] and res["derivee_de"] is None
    assert _origine_dite(res) == ["origine_illisible"]
    assert _ligne(db_path, res["grille_id"])["derivee_de_identifiant"] is None


def test_une_version_illisible_garde_l_origine_sans_sa_version(client, decor):
    gid = _grille_publiee(client, decor["p"])
    data = _retouche(_classeur(client, gid), _poser_valeur("Version tirée", "la première"))
    res = _importer(client, decor["q"], ZOE, data, nom="Sans version")
    assert res["derivee_de"] == {"nom": "Signaux", "version": None}
    assert _origine_dite(res) == ["origine_version_illisible"]


def test_le_bilan_a_blanc_dit_d_ou_elle_viendra_sans_rien_ecrire(client, decor, db_path):
    gid = _grille_publiee(client, decor["p"])
    n = _q(db_path, "SELECT COUNT(*) AS n FROM grille")[0]["n"]
    res = _importer(client, decor["q"], ZOE, _classeur(client, gid), nom="À blanc",
                    a_blanc="true")
    assert res["derivee_de"] == {"nom": "Signaux", "version": 1} and not res["ecrit"]
    assert _q(db_path, "SELECT COUNT(*) AS n FROM grille")[0]["n"] == n


# --------------------------------------------------------------------------- #
# Toute naissance a son identifiant ; l'outil écrit l'origine aussi
# --------------------------------------------------------------------------- #
def test_toute_grille_nait_avec_son_identifiant(client, decor, db_path):
    importer(client, decor["p"], LEA, nom="Importée")
    ok(client.post(f"/api/projets/{decor['p']}/grilles", headers=LEA,
                   json={"nom": "Construite", "ouverte": True}), 201)
    ok(client.post(f"/api/projets/{decor['p']}/grilles", headers=LEA,
                   json={"nom": "Construite fermée"}), 201)
    lignes = _q(db_path, "SELECT nom, identifiant FROM grille")
    assert len(lignes) == 3
    assert all(grilles.identifiant_lu(l["identifiant"]) == l["identifiant"] for l in lignes)
    assert len({l["identifiant"] for l in lignes}) == 3
    # L'index unique la garde : deux grilles ne partagent pas un identifiant.
    with pytest.raises(sqlite3.IntegrityError):
        c = sqlite3.connect(db_path)
        try:
            c.execute("UPDATE grille SET identifiant = ? WHERE nom = 'Construite'",
                      (lignes[0]["identifiant"],))
        finally:
            c.close()


def test_l_outil_ecrit_l_origine_par_le_meme_coeur(client, decor, db_path, data_dir,
                                                  tmp_path):
    source = _grille_publiee(client, decor["p"])
    fichier = tmp_path / "signaux.xlsx"
    fichier.write_bytes(_classeur(client, source))
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(data_dir),
           "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run([sys.executable, os.path.join(RACINE, "tools", "importer_grille.py"),
                        str(fichier), "--projet", str(decor["q"]), "--nom", "Par l'outil"],
                       env=env, capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    assert "dérivée de « Signaux », v1" in p.stderr
    d = _q(db_path, "SELECT * FROM grille WHERE nom = 'Par l''outil'")[0]
    assert (d["derivee_de_nom"], d["derivee_de_version"]) == ("Signaux", 1)
    assert d["derivee_de_identifiant"] == _ligne(db_path, source)["identifiant"]
    assert d["identifiant"] != d["derivee_de_identifiant"]


def test_l_origine_ne_sort_pas_du_csv_machine(client, decor):
    """Le format machine (deux CSV dans un zip) ne porte pas d'origine : réimporté, il ne
    fait pas une dérivée."""
    gid = _grille_publiee(client, decor["p"])
    r = client.get(f"/api/grilles/{gid}/versions/1/tableur?format=csv", headers=LEA)
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        texte = "".join(z.read(n).decode("utf-8-sig") for n in z.namelist())
    assert _ligne_identifiant(client, decor, gid) not in texte


def _ligne_identifiant(client, decor, gid):
    plan = ok(client.get(f"/api/grilles/{gid}/versions/1", headers=LEA))
    assert "identifiant" not in plan["grille"], "l'identifiant ne sort pas à l'écran"
    return _feuille_grille(_classeur(client, gid))["Identifiant de la grille"]
