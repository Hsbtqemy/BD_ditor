"""IMG-1 — un dérivé régénéré se revoit sans vider le cache, et revalider ne coûte rien.

La route `GET /derivatives/…` sert l'image web de chaque planche. Mesuré le 2026-09-16 : elle
ne posait aucun `Cache-Control`, si bien qu'un navigateur pouvait resservir, par fraîcheur
heuristique, un dérivé qu'on venait de régénérer avec `tools/regenerer_derives.py`. Et elle
ne répondait jamais 304 : `FileResponse` ignore `If-None-Match`, là où le montage
`StaticFiles` qu'elle a remplacé savait le faire. `no-cache` seul aurait donc fait
retélécharger chaque dérivé à chaque affichage.

**Un ordre qui ne se voit pas, et le dernier test le garde** : le 304 se décide APRÈS le
contrôle de portée. Répondre « inchangé » là où l'on doit répondre 404 dirait qu'une image
existe à ce chemin — exactement ce que le cloisonnement refuse de dire.
"""
import io
import os
import sqlite3
import time

from PIL import Image

from conftest import ADMIN


def _derive(client, planche):
    return client.get("/" + planche["chemin_web"])


def test_le_derive_se_revalide_toujours(client, planche):
    r = _derive(client, planche)
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-cache"
    assert r.headers.get("etag"), "sans ETag, aucune revalidation n'est possible"


def test_un_etag_qui_concorde_rend_304_sans_corps(client, planche):
    etag = _derive(client, planche).headers["etag"]
    r = client.get("/" + planche["chemin_web"], headers={"If-None-Match": etag})
    assert r.status_code == 304, r.status_code
    assert r.content == b""
    assert r.headers.get("etag") == etag
    assert r.headers.get("cache-control") == "no-cache"


def test_la_liste_d_etags_et_la_forme_faible_sont_comprises(client, planche):
    """La syntaxe qu'un navigateur ou un proxy envoie réellement : plusieurs ETags séparés
    par des virgules, et la forme faible `W/`."""
    etag = _derive(client, planche).headers["etag"]
    r = client.get("/" + planche["chemin_web"],
                   headers={"If-None-Match": f'"autre", W/{etag}'})
    assert r.status_code == 304


def test_un_etag_perime_rend_le_derive_regenere(client, planche, data_dir):
    """Le cas qui a fait écrire ce module : l'ancien ETag, présenté après régénération,
    doit ramener la NOUVELLE image, et non un 304 qui garderait l'ancienne à l'écran."""
    ancien = _derive(client, planche).headers["etag"]
    fichier = data_dir / planche["chemin_web"]
    buf = io.BytesIO()
    Image.new("RGB", (123, 45), "black").save(buf, "JPEG")
    fichier.write_bytes(buf.getvalue())
    futur = time.time() + 60                      # un mtime DIFFÉRENT, quelle que soit l'horloge
    os.utime(fichier, (futur, futur))

    r = client.get("/" + planche["chemin_web"], headers={"If-None-Match": ancien})
    assert r.status_code == 200
    assert r.headers["etag"] != ancien
    assert Image.open(io.BytesIO(r.content)).size == (123, 45)


def test_le_304_ne_passe_jamais_devant_la_portee(client, db_path, png_bytes, derriere_proxy):
    """Un ETag EXACT, présenté par quelqu'un qui ne voit pas l'album, reçoit 404 — pas 304.

    Le contrepoint est dans le même test : la même personne obtient bien un 304 sur l'album
    qu'elle voit, sans quoi le 404 pourrait venir d'un 304 simplement cassé.
    """
    visible = client.post("/api/albums", json={"titre": "Visible"}, headers=ADMIN).json()
    cache = client.post("/api/albums", json={"titre": "Caché"}, headers=ADMIN).json()
    pl_visible = client.post(f"/api/albums/{visible['id']}/import", headers=ADMIN,
                             files={"file": ("p.png", png_bytes, "image/png")}).json()
    pl_cache = client.post(f"/api/albums/{cache['id']}/import", headers=ADMIN,
                           files={"file": ("p.png", png_bytes, "image/png")}).json()
    conn = sqlite3.connect(db_path)
    try:
        cid = conn.execute("INSERT INTO collection (nom) VALUES ('Ouverte à bob')").lastrowid
        conn.execute("DELETE FROM collection_album WHERE album_id = ?", (visible["id"],))
        conn.execute("INSERT INTO collection_album (collection_id, album_id) VALUES (?, ?)",
                     (cid, visible["id"]))
        conn.execute("INSERT INTO collection_acces (collection_id, genre, principal, niveau) "
                     "VALUES (?, 'utilisateur', 'bob', 'lecture')", (cid,))
        conn.commit()
    finally:
        conn.close()

    etag_cache = client.get("/" + pl_cache["chemin_web"], headers=ADMIN).headers["etag"]
    etag_visible = client.get("/" + pl_visible["chemin_web"], headers=ADMIN).headers["etag"]
    bob = {"Remote-User": "bob"}

    r = client.get("/" + pl_cache["chemin_web"], headers={**bob, "If-None-Match": etag_cache})
    assert r.status_code == 404, (
        f"{r.status_code} : un ETag exact a franchi le cloisonnement")
    r = client.get("/" + pl_visible["chemin_web"],
                   headers={**bob, "If-None-Match": etag_visible})
    assert r.status_code == 304
