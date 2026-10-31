"""Un DÉTAIL ne sort pas de l'instance avant la tranche 4 (ANN-7, tranche 2, commit 9 ; G17).

Le patron de `test_releves_sorties.py` et de `test_le_projet_ne_sort_d_aucun_artefact` : une
base semée d'un détail à marques SENTINELLES — son nom, sa note ; un relevé y est posé
—, chaque artefact produit (les trois exports d'album, la
recherche exportée, la voie du dépôt, les outils de sortie), et les marques absentes de
chacun. Le semis est son propre témoin : ce qu'on cherche par son absence est d'abord vu là
où il doit être (les régions de la planche, la note de la région), et une bulle TÉMOIN, semée
à côté, est vue dans chaque sortie qui porte des régions — sans quoi une sortie vide
passerait pour une sortie propre.

`database.sql_region_sortante` est le point d'appel unique de la règle ; ce fichier ne la
recopie pas, il la JOUE.

Le détail porte aussi un TAG, qu'il est seul à porter, et ce tag n'est PAS une marque : un tag
est du VOCABULAIRE, que les sorties disent par appartenance (le catalogue des termes d'une
collection, AUTH-11), qu'il soit posé ou non. Ce qui ne sort pas, c'est son EMPLOI sur le
détail — la ligne d'annotation du détail, que sa note désigne.
"""
import csv
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path

import pytest

import database
from conftest import REPO_ROOT
from grilles_decor import csv_de, importer

NOM, NOTE, TAG = "ZZDETAIL9", "ZZNOTEDET9", "zztagdet9"
MARQUES = (NOM, NOTE)
TEMOIN = "OUILLE TEMOIN"


def _outil(db_path, outil, *args):
    env = {**os.environ, "BD_DB_PATH": str(db_path), "BD_DATA_DIR": str(db_path.parent)}
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / outil), *args],
                       cwd=str(REPO_ROOT), env=env, capture_output=True)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def _fouillable(blob: bytes) -> str:
    if blob[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            return "\n".join(z.read(n).decode("utf-8", "replace") for n in z.namelist())
    return blob.decode("utf-8", "replace")


def semer(client, png_bytes):
    """Un album d'une collection publique : une case, une bulle témoin, un DÉTAIL nommé,
    annoté, tagué, retouché (son nom changé : le journal porte deux actes sur lui), et un
    relevé d'une grille qui vise le détail. Mono-poste : la portée est totale."""
    projet = next(p for p in client.get("/api/projets").json() if p["repli"])["id"]
    cid = client.post("/api/collections",
                      json={"nom": "Déposée", "projet_id": projet}).json()["id"]
    client.patch(f"/api/collections/{cid}", json={"statut_diffusion": "public"})
    aid = client.post("/api/albums", json={"titre": "Album", "collection_id": cid}).json()["id"]
    pl = client.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", png_bytes, "image/png")}).json()
    case = client.post(f"/api/planches/{pl['id']}/regions",
                       json={"type": "case", "x": 0, "y": 0, "w": 40, "h": 40}).json()
    bulle = client.post(f"/api/planches/{pl['id']}/regions",
                        json={"type": "bulle", "x": 1, "y": 1, "w": 9, "h": 9,
                              "parent_id": case["id"]}).json()
    assert client.put(f"/api/regions/{bulle['id']}",
                      json={"ocr_texte": TEMOIN}).status_code == 200
    r = client.post(f"/api/planches/{pl['id']}/regions",
                    json={"type": "detail", "x": 20, "y": 20, "w": 9, "h": 9,
                          "parent_id": case["id"], "nom": "brouillon"})
    assert r.status_code == 201, r.text
    detail = r.json()
    assert client.put(f"/api/regions/{detail['id']}",
                      json={"nom": NOM, "vu": {"nom": "brouillon"}}).status_code == 200
    assert client.put(f"/api/regions/{detail['id']}/annotation",
                      json={"note": NOTE, "tags_ajoutes": [TAG]}).status_code == 200
    # Un second détail, nommé puis SUPPRIMÉ : le journal garde ses actes, et ne les publie pas.
    parti = client.post(f"/api/planches/{pl['id']}/regions",
                        json={"type": "detail", "x": 30, "y": 30, "w": 5, "h": 5,
                              "parent_id": case["id"], "nom": NOM + "PARTI"}).json()
    assert client.put(f"/api/regions/{parti['id']}/annotation",
                      json={"note": NOTE + "PARTI"}).status_code == 200
    assert client.delete(f"/api/regions/{parti['id']}").status_code == 204
    # Un troisième, nommé puis supprimé sans rien d'autre : seuls ses actes `regions` disent
    # son type (commit 10 : la clé `journal.CLE_REGION_RETENUE` n'y est pas, l'instantané
    # le dit déjà).
    nu = client.post(f"/api/planches/{pl['id']}/regions",
                     json={"type": "detail", "x": 32, "y": 32, "w": 3, "h": 3,
                           "parent_id": case["id"], "nom": NOM + "NU"}).json()
    assert client.delete(f"/api/regions/{nu['id']}").status_code == 204
    entete = ["cle", "forme", "libelle", "cible"]
    tableur = csv_de([entete, ["objet", "simple", "objet montré", "detail"]])
    gid = importer(client, projet, {}, entrees=tableur, listes=None, nom="Objets",
                   porte_sur="detail")["grille_id"]
    client.post(f"/api/grilles/{gid}/versions/1/publication")
    client.put(f"/api/projets/{projet}/grilles/{gid}/activation", json={"version": 1})
    rel = client.post("/api/releves", json={"grille_id": gid, "version": 1,
                                            "region_id": detail["id"], "entree_cle": "objet"})
    assert rel.status_code == 201, rel.text
    return {"collection": cid, "album": aid, "planche": pl["id"], "detail": detail["id"],
            "parti": parti["id"], "nu": nu["id"], "bulle": bulle["id"], "case": case["id"],
            "releve": rel.json()["id"]}


def _sorties(client, db_path, tmp_path, s):
    """Chaque artefact qui QUITTE l'instance, par son chemin : son texte fouillable."""
    sorties = {}
    a, c = s["album"], s["collection"]
    for chemin in (f"/api/export/json?album_id={a}", f"/api/export/csv?album_id={a}",
                   f"/api/export/tei?album_id={a}",
                   "/api/recherche/export.csv?q=" + NOTE,
                   "/api/recherche/export.csv?q=TEMOIN",
                   f"/api/collections/{c}/depot/description",
                   f"/api/collections/{c}/depot/description?format=csv",
                   f"/api/collections/{c}/depot/metadonnees",
                   f"/api/collections/{c}/depot/metadonnees?format=zip",
                   f"/api/collections/{c}/depot/metadonnees?format=zip&verbatim=1",
                   f"/api/collections/{c}/depot/iiif?base_url=https://images.example.org"):
        r = client.get(chemin)
        assert r.status_code == 200, (chemin, r.text[:300])
        sorties[chemin] = _fouillable(r.content)
    for outil, args, produits in (
            ("description_collection.py", ["--json", "-"], []),
            ("description_collection.py", ["--json", "-", "--collection", str(c)], []),
            ("metadonnees_collection.py", ["--json", "-"], []),
            ("metadonnees_collection.py", ["--json", "-", "--verbatim"], []),
            ("metadonnees_collection.py", ["--csv-dir", str(tmp_path / "csv")],
             [tmp_path / "csv"]),
            ("metadonnees_collection.py", ["--csv-dir", str(tmp_path / "csvc"),
                                           "--collection", str(c)], [tmp_path / "csvc"]),
            ("crosswalk_depot.py", ["--out-dir", str(tmp_path / "cw")], [tmp_path / "cw"]),
            ("provenance_export.py", ["--out-dir", str(tmp_path / "prov")],
             [tmp_path / "prov"]),
            ("iiif_manifest.py", ["--base-url", "http://exemple/iiif", "--out-dir",
                                  str(tmp_path / "iiif")], [tmp_path / "iiif"])):
        code, out, err = _outil(db_path, outil, *args)
        assert code == 0, (outil, args, err[-600:])
        fichiers = [f for d in produits for f in Path(d).glob("**/*") if f.is_file()]
        sorties[f"{outil} {' '.join(args[:1] + args[2:])}"] = out + err + "\n".join(
            _fouillable(f.read_bytes()) for f in fichiers)
    return sorties


# Les sorties qui portent des RÉGIONS : la bulle témoin y est, sans quoi l'absence du détail
# ne prouverait rien. Les autres (descriptions, provenance, crosswalk) comptent ou datent.
PORTENT_LE_TEXTE = ("/api/export/json", "/api/export/csv", "/api/export/tei",
                    "q=TEMOIN", "verbatim")


def test_un_detail_ne_sort_d_aucun_artefact(client, db_path, tmp_path, png_bytes):
    s = semer(client, png_bytes)
    # Le semis est son propre témoin : le détail VIT dans l'instance.
    regions = client.get(f"/api/planches/{s['planche']}/regions").json()
    det = next(r for r in regions if r["id"] == s["detail"])
    assert det["type"] == "detail" and det["nom"] == NOM
    ann = client.get(f"/api/regions/{s['detail']}/annotation").json()
    assert ann["note"] == NOTE and [t["label"] for t in ann["tags"]] == [TAG]
    assert any(r["region_id"] == s["detail"]
               for r in client.get(f"/api/planches/{s['planche']}/releves").json()["releves"])
    d, x, nu = s["detail"], s["parti"], s["nu"]
    # Un troisième détail, né SANS acte de création — comme une région recopiée par une
    # copie amorcée (aucun événement n'est recopié, E3) —, puis annoté par la route : le
    # journal ne le dit d'aucun type, et seule la région vivante le désigne.
    conn = sqlite3.connect(db_path)
    try:
        sans = conn.execute(
            "INSERT INTO regions (planche_id, parent_id, type, x, y, w, h, ordre, source, nom) "
            "VALUES (?, NULL, 'detail', 2, 2, 4, 4, 9, 'manuel', ?)",
            (s["planche"], NOM + "SANS")).lastrowid
        conn.commit()
    finally:
        conn.close()
    assert client.put(f"/api/regions/{sans}/annotation",
                      json={"note": NOTE + "SANS"}).status_code == 200
    # Commit 10 — une note changée puis défaite par Ctrl+Z : l'annulation désigne l'acte sur
    # le détail, et ne sort pas plus que lui.
    assert client.put(f"/api/regions/{sans}/annotation",
                      json={"note": NOTE + "SANS2"}).status_code == 200
    assert client.post("/api/undo").status_code == 200
    # Et un quatrième, né sans acte, dont le seul acte a été écrit AVANT le commit 10, sans
    # la clé `journal.CLE_REGION_RETENUE` : c'est la région vivante qui le dit retenu.
    conn = sqlite3.connect(db_path)
    try:
        vieux = conn.execute(
            "INSERT INTO regions (planche_id, parent_id, type, x, y, w, h, ordre, source) "
            "VALUES (?, NULL, 'detail', 3, 3, 2, 2, 10, 'manuel')", (s["planche"],)).lastrowid
        conn.execute("INSERT INTO evenement (type, agent_type, cible_table, cible_id, avant, "
                     "apres) VALUES ('modification', 'humain', 'annotations', ?, ?, ?)",
                     (vieux, '{"note": "x", "tags": []}', '{"note": "y", "tags": []}'))
        conn.commit()
    finally:
        conn.close()
    # Le journal garde les actes des détails — le supprimé compris (création, note,
    # suppression) : c'est ce que le journal PUBLIÉ doit taire.
    conn = sqlite3.connect(db_path)
    try:
        actes = {cid: n for cid, n in conn.execute(
            "SELECT cible_id, COUNT(*) FROM evenement WHERE cible_table IN "
            "('regions', 'annotations') AND cible_id IN (?, ?, ?) GROUP BY cible_id",
            (d, x, sans))}
        sur_un_detail = [str(i) for (i,) in conn.execute(
            "SELECT id FROM evenement WHERE cible_table IN ('regions', 'annotations') "
            "AND cible_id IN (?, ?, ?, ?, ?)", (d, x, sans, nu, vieux))]
        assert conn.execute("SELECT COUNT(*) FROM evenement WHERE type = 'annulation' AND "
                            f"cible_id IN ({','.join(sur_un_detail)})").fetchone()[0] == 1
    finally:
        conn.close()
    assert actes.get(d, 0) >= 3 and actes.get(x, 0) >= 3 and actes.get(sans, 0) >= 1, actes
    sorties = _sorties(client, db_path, tmp_path, s)
    # Ce qui désignerait le détail sans le nommer : son type, ses ancres dans le TEI, l'IIIF
    # et le journal de provenance — le vivant comme le supprimé.
    ids = f"{d}|{x}|{sans}|{nu}|{vieux}"
    actes_ids = "|".join(sur_un_detail)
    designations = re.compile(rf"\bdetail\b|zone_({ids})\b|region-({ids})\b"
                              rf"|(regions|annotations)/({ids})\b|evenement/({actes_ids})\b")
    for surface, texte in sorties.items():
        assert len(texte) > 40, f"{surface} : sortie vide, le contrôle ne mesure rien"
        for interdit in MARQUES:
            assert interdit not in texte, f"{surface} laisse sortir « {interdit} »"
        m = designations.search(texte)
        extrait = texte[max(0, m.start() - 60):m.end() + 60] if m else ""
        assert m is None, f"{surface} désigne le détail : « {extrait} »"
        if any(k in surface for k in PORTENT_LE_TEXTE):
            assert TEMOIN in texte, (f"{surface} : la bulle témoin n'y est pas, le contrôle "
                                     "ne mesure rien")


def test_un_detail_ne_se_cite_pas(client, png_bytes):
    s = semer(client, png_bytes)
    r = client.post("/api/figures", json={"regions": [s["detail"]],
                                          "collection_id": s["collection"]})
    assert r.status_code == 422, r.text
    assert "détail" in r.json()["detail"]
    # La bulle du même album se cite : le refus porte sur le détail, pas sur l'album.
    assert client.post("/api/figures", json={"regions": [s["bulle"]],
                                             "collection_id": s["collection"]}).status_code == 200


# --------------------------------------------------------------------------- #
# Relecture croisée du commit 9 (ANN-7, tranche 2, commit 10)
# --------------------------------------------------------------------------- #
def _publies(db_path):
    """Les actes que le journal PUBLIÉ porte (`_commun.evenements_publiables`)."""
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import _commun
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        return [dict(e) for e in _commun.evenements_publiables(c)]
    finally:
        c.close()


def _lignes(fichier):
    with open(fichier, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_le_resume_de_provenance_compte_ce_qui_est_publie(client, db_path, tmp_path,
                                                          png_bytes):
    """Constat 1 — le résumé de provenance (`journal.indicateurs_provenance`) des métadonnées
    et de la description comptait le détail : ses régions dans `regions`, ses actes dans
    `evenements`. Des NOMBRES, comparés à ce que le même artefact publie : une marque ne s'y
    voit pas, et le cliquet de marques était resté vert."""
    s = semer(client, png_bytes)
    publies = _publies(db_path)
    assert publies, "le journal publié est vide : la comparaison ne mesure rien"
    code, out, err = _outil(db_path, "metadonnees_collection.py", "--json", "-")
    assert code == 0, err
    prov = json.loads(out)["metadonnees_collection"]["paradonnee"]["provenance"]
    code, out, err = _outil(db_path, "metadonnees_collection.py",
                            "--csv-dir", str(tmp_path / "t"))
    assert code == 0, err
    regions = _lignes(tmp_path / "t" / "regions.csv")
    evenements = _lignes(tmp_path / "t" / "evenement.csv")
    # Les régions : celles que l'artefact publie — la case et la bulle témoin, pas le détail.
    assert prov["regions"]["total"] == len(regions) == 2, (prov["regions"], len(regions))
    # Les actes : ceux de la table publiée, au nombre, par type, par agent, et ses bornes.
    ev = prov["evenements"]
    assert ev["total"] == len(publies) == len(evenements), (ev["total"], len(publies))
    assert ev["par_type"] == dict(Counter(e["type"] for e in publies))
    assert ev["par_agent"] == dict(Counter(e["agent_type"] for e in publies))
    assert (ev["premier"], ev["dernier"]) == (min(e["date"] for e in publies),
                                              max(e["date"] for e in publies))
    # La description dit les mêmes nombres, par la route comme par l'outil, et son audit
    # compte les régions comme sa couverture.
    d = client.get(f"/api/collections/{s['collection']}/depot/description").json()
    d = d["description_collection"]
    audit = d["provenance_globale"]["audit"]
    assert audit["regions"]["total"] == d["couverture"]["regions"]["total"] == 2
    assert audit["evenements"]["total"] == len(publies)
    code, out, err = _outil(db_path, "description_collection.py", "--json", "-")
    assert code == 0, err
    audit = json.loads(out)["description_collection"]["provenance_globale"]["audit"]
    assert audit["regions"]["total"] == 2 and audit["evenements"]["total"] == len(publies)


def _amorcee(client, s):
    """Une copie AMORCÉE au cran du découpage, dans une autre collection du même projet :
    ses régions — le détail compris — naissent SANS acte (E3)."""
    projet = next(p for p in client.get("/api/projets").json() if p["repli"])["id"]
    etude = client.post("/api/collections", json={"nom": "Étude", "projet_id": projet}).json()
    doc = next(a for a in client.get("/api/albums").json() if a["id"] == s["album"])
    r = client.post(f"/api/collections/{etude['id']}/prendre", json={"documents": [
        {"document_id": doc["document_id"], "reponse": "amorcer", "album_id": s["album"],
         "cran": "decoupage"}]})
    assert r.status_code == 200, r.text
    (ligne,) = r.json()["documents"]
    assert ligne["etat"] == "fait", ligne
    copie = ligne["copie_id"]
    (pl,) = client.get(f"/api/albums/{copie}/planches").json()
    regions = client.get(f"/api/planches/{pl['id']}/regions").json()
    det = next(x for x in regions if x["type"] == "detail")
    bulle = next(x for x in regions if x["type"] == "bulle")
    return {"album": copie, "planche": pl["id"], "detail": det["id"],
            "case": det["parent_id"], "bulle": bulle["id"]}


@pytest.mark.parametrize("emporter", ["case", "planche", "album", "repartir"])
def test_un_detail_ne_sans_acte_ne_sort_pas_apres_sa_cascade(client, db_path, tmp_path,
                                                             png_bytes, emporter):
    """Constat 2 — un détail NÉ SANS ACTE (une région recopiée par une copie amorcée, E3),
    annoté, puis emporté par la cascade de sa case, de sa planche, de son album, ou par une
    remise à zéro au cran des images : plus rien ne le disait d'un type retenu, et l'acte sur
    sa note partait au dépôt. L'acte porte désormais le type de sa région
    (`journal.CLE_REGION_RETENUE`), écrit quand la région existe."""
    s = semer(client, png_bytes)
    c = _amorcee(client, s)
    sans = c["detail"]
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM evenement WHERE cible_table = 'regions' "
                            "AND cible_id = ?", (sans,)).fetchone()[0] == 0, \
            "la copie a un acte sur son détail : le cas n'est pas celui qu'on mesure"
    finally:
        conn.close()
    for rid in (sans, c["bulle"]):
        assert client.put(f"/api/regions/{rid}/annotation",
                          json={"note": NOTE + "COPIE"}).status_code == 200
    r = {"case": lambda: client.delete(f"/api/regions/{c['case']}"),
         "planche": lambda: client.delete(f"/api/planches/{c['planche']}"),
         "album": lambda: client.delete(f"/api/albums/{c['album']}"),
         "repartir": lambda: client.post(f"/api/albums/{c['album']}/repartir",
                                         json={"cran": "images"})}[emporter]()
    assert r.status_code in (200, 204), r.text
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT 1 FROM regions WHERE id = ?", (sans,)).fetchone() is None
        assert conn.execute("SELECT COUNT(*) FROM evenement WHERE cible_table = "
                            "'annotations' AND cible_id = ?", (sans,)).fetchone()[0] == 1
    finally:
        conn.close()
    assert not [e for e in _publies(db_path) if e["cible_id"] == sans
                and e["cible_table"] == "annotations"], "l'acte sur la note du détail sort"
    code, out, err = _outil(db_path, "provenance_export.py", "--out-dir", str(tmp_path / "p"))
    assert code == 0, err
    texte = "\n".join(f.read_text("utf-8") for f in (tmp_path / "p").glob("**/*")
                      if f.is_file())
    assert f"annotations/{sans}" not in texte, "l'acte sur la note du détail est publié"
    # Le témoin : la bulle de la copie, annotée et emportée par le même chemin, sort, elle —
    # la coupure porte sur le détail, pas sur ce que la cascade a emporté.
    assert f"annotations/{c['bulle']}" in texte, "le témoin ne sort pas : rien n'est mesuré"


def _rangs_csv(texte, colonne_id):
    """`{region_id: ordre}` d'une table de régions en CSV."""
    return {int(l[colonne_id]): int(l["ordre"]) for l in csv.DictReader(io.StringIO(texte))}


def test_l_ordre_publie_n_a_pas_de_trou(client, db_path, tmp_path, png_bytes):
    """L'ordre STOCKÉ suit la lecture, détails compris ; chaque sortie qui publie `ordre` le
    renumérote 1..N sans eux (`database.rangs_de_sortie`). Sans quoi la bulle du milieu sortait
    à l'ordre 3 sous une bulle à l'ordre 1, et le trou disait qu'une région retenue y est."""
    s = semer(client, png_bytes)
    pid, case = s["planche"], s["case"]
    # Le détail du semis est à (20, 20) : une bulle à sa droite vient APRÈS lui en lecture.
    apres = client.post(f"/api/planches/{pid}/regions",
                        json={"type": "bulle", "x": 34, "y": 21, "w": 4, "h": 4,
                              "parent_id": case}).json()["id"]
    bulle = s["bulle"]
    # La fratrie du semis, rangée par lecture à la main : témoin, détail, bulle d'après.
    conn = sqlite3.connect(db_path)
    with conn:
        for rang, rid in enumerate((bulle, s["detail"], apres), start=1):
            conn.execute("UPDATE regions SET ordre = ? WHERE id = ?", (rang, rid))
    conn.close()
    lu = {r["id"]: r for r in client.get(f"/api/planches/{pid}/regions").json()}
    assert (lu[bulle]["ordre"], lu[s["detail"]]["ordre"], lu[apres]["ordre"]) == (1, 2, 3)

    attendu = {bulle: 1, apres: 2}
    a, c = s["album"], s["collection"]
    # L'export JSON de l'album.
    album = client.get(f"/api/export/json?album_id={a}").json()
    arbre = next(x for x in album["planches"][0]["regions"] if x["id"] == case)
    assert {e["id"]: e["ordre"] for e in arbre["enfants"]} == attendu
    # L'export CSV de l'album.
    texte = client.get(f"/api/export/csv?album_id={a}").text
    assert {k: v for k, v in _rangs_csv(texte, "region_id").items() if k in attendu} == attendu
    # Les métadonnées, par la voie du dépôt et par l'outil : l'arbre JSON et la table CSV.
    def arbre_de(d):
        racines = d["metadonnees_collection"]["albums"][0]["planches"][0]["regions"]
        return {e["id"]: e["ordre"] for e in next(x for x in racines
                                                  if x["id"] == case)["enfants"]}
    assert arbre_de(client.get(f"/api/collections/{c}/depot/metadonnees").json()) == attendu
    code, out, err = _outil(db_path, "metadonnees_collection.py", "--json", "-")
    assert code == 0, err
    assert arbre_de(json.loads(out)) == attendu
    code, out, err = _outil(db_path, "metadonnees_collection.py",
                            "--csv-dir", str(tmp_path / "ordre"))
    assert code == 0, err
    table = _rangs_csv((tmp_path / "ordre" / "regions.csv").read_text("utf-8-sig"), "id")
    assert {k: v for k, v in table.items() if k in attendu} == attendu
    assert s["detail"] not in table


def test_le_rang_publie_est_par_fratrie_et_sans_trou():
    """La règle seule : par planche ET par parent, l'ordre stocké puis l'identifiant, un ordre
    absent d'abord — comme le tri des exports. Mutant tué : une fratrie qui ignore la planche."""
    lignes = [{"id": 1, "planche_id": 1, "parent_id": None, "ordre": 4},
              {"id": 2, "planche_id": 1, "parent_id": None, "ordre": 9},
              {"id": 3, "planche_id": 1, "parent_id": 1, "ordre": 2},
              {"id": 4, "planche_id": 1, "parent_id": 1, "ordre": 2},
              {"id": 5, "planche_id": 1, "parent_id": 1, "ordre": None},
              {"id": 6, "planche_id": 2, "parent_id": None, "ordre": 7}]
    assert database.rangs_de_sortie(lignes) == {1: 1, 2: 2, 5: 1, 3: 2, 4: 3, 6: 1}
    assert database.rangs_de_sortie([{"region_id": 8, "planche_id": 1, "parent_id": None,
                                      "ordre": 3}], cle="region_id") == {8: 1}
