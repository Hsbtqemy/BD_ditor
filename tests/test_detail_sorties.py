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
import io
import os
import re
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

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
            "parti": parti["id"], "bulle": bulle["id"], "releve": rel.json()["id"]}


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
    d, x = s["detail"], s["parti"]
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
    # Le journal garde les actes des détails — le supprimé compris (création, note,
    # suppression) : c'est ce que le journal PUBLIÉ doit taire.
    conn = sqlite3.connect(db_path)
    try:
        actes = {cid: n for cid, n in conn.execute(
            "SELECT cible_id, COUNT(*) FROM evenement WHERE cible_table IN "
            "('regions', 'annotations') AND cible_id IN (?, ?, ?) GROUP BY cible_id",
            (d, x, sans))}
    finally:
        conn.close()
    assert actes.get(d, 0) >= 3 and actes.get(x, 0) >= 3 and actes.get(sans, 0) >= 1, actes
    sorties = _sorties(client, db_path, tmp_path, s)
    # Ce qui désignerait le détail sans le nommer : son type, ses ancres dans le TEI, l'IIIF
    # et le journal de provenance — le vivant comme le supprimé.
    designations = re.compile(rf"\bdetail\b|zone_({d}|{x}|{sans})\b|region-({d}|{x}|{sans})\b"
                              rf"|(regions|annotations)/({d}|{x}|{sans})\b")
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
