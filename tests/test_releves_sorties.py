"""Rien des grilles ni des relevés ne sort de l'instance en tranche 1 (ANN-7 ; cadrage R12).

Le patron de `test_le_projet_ne_sort_d_aucun_artefact` : une base semée d'une grille et de
relevés à marques SENTINELLES — le nom de la grille, une entrée, une variante, une précision,
un message de doute —, chaque artefact produit (les trois exports d'album, la voie du dépôt,
les outils de sortie), et les marques absentes de chacun. Le semis est son propre témoin : ce
qu'on cherche par son absence est d'abord vu là où il doit être (la route des relevés).
"""
import io
import os
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

from conftest import REPO_ROOT
from grilles_decor import csv_de, importer

MARQUES = ("ZZGRILLE7", "ZZENTREE7", "zzcle7", "ZZVARIANTE7", "ZZPRECIS7", "ZZDOUTE7")


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
    """Un album d'une collection publique, une grille active, un relevé à variante et
    précision, un doute ouvert — tout en mono-poste, où la portée est totale."""
    projet = next(p for p in client.get("/api/projets").json() if p["repli"])["id"]
    cid = client.post("/api/collections", json={"nom": "Déposée", "projet_id": projet}).json()["id"]
    client.patch(f"/api/collections/{cid}", json={"statut_diffusion": "public"})
    aid = client.post("/api/albums", json={"titre": "Album", "collection_id": cid}).json()["id"]
    pl = client.post(f"/api/albums/{aid}/import",
                     files={"file": ("p.png", png_bytes, "image/png")}).json()
    bulle = client.post(f"/api/planches/{pl['id']}/regions",
                        json={"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9}).json()
    client.put(f"/api/regions/{bulle['id']}", json={"ocr_texte": "OUILLE"})
    entete = ["cle", "forme", "libelle", "variante_cle", "variante", "precision"]
    tableur = csv_de([entete, ["zzcle7", "variantes", "ZZENTREE7", "", "", "le lieu"],
                      ["zzcle7", "", "", "v", "ZZVARIANTE7", ""]])
    gid = importer(client, projet, {}, entrees=tableur, listes=None, nom="ZZGRILLE7")["grille_id"]
    client.post(f"/api/grilles/{gid}/versions/1/publication")
    client.put(f"/api/projets/{projet}/grilles/{gid}/activation", json={"version": 1})
    r = client.post("/api/releves", json={"grille_id": gid, "version": 1,
                                          "region_id": bulle["id"], "entree_cle": "zzcle7",
                                          "variante_cle": "v", "mots": [0],
                                          "precision": "ZZPRECIS7"})
    assert r.status_code == 201, r.text
    d = client.post(f"/api/releves/{r.json()['id']}/doutes", json={"texte": "ZZDOUTE7"})
    return {"projet": projet, "collection": cid, "album": aid, "planche": pl["id"],
            "grille": gid, "doute": d.status_code}


def test_rien_des_releves_ne_sort_d_aucun_artefact(client, db_path, tmp_path, png_bytes):
    s = semer(client, png_bytes)
    temoin = client.get(f"/api/planches/{s['planche']}/releves").text + client.get(
        f"/api/grilles/{s['grille']}/versions/1").text
    attendues = [m for m in MARQUES if m != "ZZDOUTE7" or s["doute"] in (200, 201)]
    assert all(m in temoin for m in attendues), "le semis ne pose pas ce qu'on cherche"
    sorties = {}
    a, c = s["album"], s["collection"]
    for chemin in (f"/api/export/json?album_id={a}", f"/api/export/csv?album_id={a}",
                   f"/api/export/tei?album_id={a}", f"/api/collections/{c}/depot/description",
                   f"/api/collections/{c}/depot/description?format=csv",
                   f"/api/collections/{c}/depot/metadonnees",
                   f"/api/collections/{c}/depot/metadonnees?format=zip",
                   f"/api/collections/{c}/depot/iiif?base_url=https://images.example.org"):
        r = client.get(chemin)
        assert r.status_code == 200, (chemin, r.text[:300])
        sorties[chemin] = _fouillable(r.content)
    for outil, args, produits in (
            ("description_collection.py", ["--json", "-"], []),
            ("metadonnees_collection.py", ["--json", "-"], []),
            ("metadonnees_collection.py", ["--csv-dir", str(tmp_path / "csv")],
             [tmp_path / "csv"]),
            ("crosswalk_depot.py", ["--out-dir", str(tmp_path / "cw")], [tmp_path / "cw"]),
            ("provenance_export.py", ["--out-dir", str(tmp_path / "prov")],
             [tmp_path / "prov"]),
            ("iiif_manifest.py", ["--base-url", "http://exemple/iiif", "--out-dir",
                                  str(tmp_path / "iiif")], [tmp_path / "iiif"])):
        code, out, err = _outil(db_path, outil, *args)
        assert code == 0, (outil, err[-600:])
        fichiers = [f for d in produits for f in Path(d).glob("**/*") if f.is_file()]
        sorties[f"{outil} {args[0]}"] = out + err + "\n".join(
            _fouillable(f.read_bytes()) for f in fichiers)
    for surface, texte in sorties.items():
        assert len(texte) > 40, f"{surface} : sortie vide, le contrôle ne mesure rien"
        for interdit in (*MARQUES, "grille_id", "entree_cle"):
            assert interdit not in texte, f"{surface} laisse sortir « {interdit} »"
