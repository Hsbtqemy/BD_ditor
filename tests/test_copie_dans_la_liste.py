"""Ce que `GET /api/albums` dit d'une copie, sous les bornes tranchées par Hugo le 2026-11-02
(UX-20). Joué sur le JSON BRUT : ce qu'il faut éprouver est ce qui n'y est pas, et une lecture
par clé ne verrait ni une clé en trop ni un identifiant ailleurs dans la ligne.

- `copie_de` ne sort que si l'on lit l'original ;
- `a_moi` sort pour tous ;
- `copie_par` et `copie_par_nom` ne sortent qu'à qui écrit dans la copie et à la portée totale.
"""
import sqlite3

import pytest

from conftest import ADMIN
from test_copies_soeurs import LEA, LECTRICE, SAM, soeurs  # noqa: F401
from test_fonds import _accorder


def _ligne(client, qui, album_id):
    r = client.get("/api/albums", headers=qui)
    assert r.status_code == 200, r.text
    return next((a for a in r.json() if a["id"] == album_id), None)


def _sans_nulle_source(ligne):
    """La ligne, sans `soeur` et `derniere_copie`, qui parlent du DOCUMENT : à qui écrit dans
    la copie, ils changent quand une sœur disparaît, et c'est tranché par la 3a et la 3b."""
    return {k: ligne[k] for k in sorted(ligne) if k not in ("soeur", "derniere_copie")}


# --------------------------------------------------------------------------- #
# Le lien vers l'original
# --------------------------------------------------------------------------- #
def test_qui_lit_l_original_recoit_le_lien(client, soeurs):
    a, b = soeurs["a"], soeurs["b"]
    assert _ligne(client, ADMIN, b)["copie_de"] == a
    _accorder(client, soeurs["principale"], "lectrice", "lecture")
    assert _ligne(client, LECTRICE, b)["copie_de"] == a


def test_qui_ne_lit_pas_l_original_n_en_recoit_aucune_trace(client, soeurs, db_path):
    """Ni son identifiant, ni son titre : la lectrice et Sam ne lisent que la copie. Le titre
    de l'original est changé à part pour qu'il ne se confonde pas avec celui de la copie."""
    a, b = soeurs["a"], soeurs["b"]
    c = sqlite3.connect(db_path)
    c.execute("UPDATE albums SET titre = 'SEUL-L-ORIGINAL' WHERE id = ?", (a,))
    c.commit()
    c.close()
    for qui in (SAM, LECTRICE):
        ligne = _ligne(client, qui, b)
        assert ligne["copie_de"] is None and _ligne(client, qui, a) is None
        brut = client.get("/api/albums", headers=qui).text
        assert "SEUL-L-ORIGINAL" not in brut and "depuis_album_id" not in brut


def test_rien_ne_distingue_un_original_non_lu_d_un_original_detruit(client, soeurs):
    """Le cœur de la borne : la même ligne, à la lettre, pour qui ne lit pas l'original et
    pour qui lit une copie dont l'original n'existe plus."""
    a, b = soeurs["a"], soeurs["b"]
    avant = _ligne(client, SAM, b)
    assert client.delete(f"/api/albums/{a}", headers=ADMIN).status_code == 204
    apres = _ligne(client, SAM, b)
    assert _sans_nulle_source(avant) == _sans_nulle_source(apres)


def test_un_album_d_origine_a_la_meme_forme(client, soeurs):
    """`copie_de` est toujours là et vaut `null` : son absence ne dirait rien de plus, et
    sa présence seulement sur les copies en dirait trop."""
    ligne = _ligne(client, LEA, soeurs["a"])
    assert "copie_de" in ligne and ligne["copie_de"] is None


# --------------------------------------------------------------------------- #
# « à vous »
# --------------------------------------------------------------------------- #
def test_a_moi_sort_pour_tous_et_ne_dit_que_soi(client, soeurs):
    a, b = soeurs["a"], soeurs["b"]
    assert _ligne(client, SAM, b)["a_moi"] is True
    assert _ligne(client, LECTRICE, b)["a_moi"] is False
    assert _ligne(client, ADMIN, b)["a_moi"] is False
    assert _ligne(client, LEA, a)["a_moi"] is True, "elle a importé l'album"


def test_un_album_d_avant_le_fonds_ne_porte_aucune_marque(client, soeurs, db_path):
    """`copie.creee_par` NULL (d'avant la v30, ou le mono-poste) : ni « à vous », ni nom."""
    c = sqlite3.connect(db_path)
    c.execute("UPDATE copie SET creee_par = NULL WHERE album_id = ?", (soeurs["b"],))
    c.commit()
    c.close()
    ligne = _ligne(client, SAM, soeurs["b"])
    assert ligne["a_moi"] is False
    assert ligne["copie_par"] is None and ligne["copie_par_nom"] is None


def test_en_mono_poste_rien_n_est_a_personne(client):
    a = client.post("/api/albums", json={"titre": "Seul"}, headers=ADMIN).json()["id"]
    assert _ligne(client, ADMIN, a)["a_moi"] is False


# --------------------------------------------------------------------------- #
# Qui a fait la copie
# --------------------------------------------------------------------------- #
def test_qui_ecrit_dans_la_copie_lit_son_auteur(client, soeurs):
    ligne = _ligne(client, SAM, soeurs["b"])
    assert ligne["copie_par"] == "sam"
    client.get("/api/moi", headers={**LEA, "Remote-Name": "Lea Lecomte"})
    assert _ligne(client, LEA, soeurs["a"])["copie_par_nom"] == "Lea Lecomte"


def test_la_portee_totale_lit_son_auteur(client, soeurs):
    assert _ligne(client, ADMIN, soeurs["b"])["copie_par"] == "sam"


def test_une_lectrice_ne_recoit_pas_les_cles_du_nom(client, soeurs):
    """Absentes, pas à `null` : à `null`, elle lirait une copie sans auteur connu. Et le
    login ne traîne nulle part dans la réponse brute."""
    ligne = _ligne(client, LECTRICE, soeurs["b"])
    assert "copie_par" not in ligne and "copie_par_nom" not in ligne
    assert '"sam"' not in client.get("/api/albums", headers=LECTRICE).text


def test_un_responsable_qui_lit_sans_ecrire_ne_lit_pas_le_nom(client, soeurs):
    """La borne est celle de `repartie` : écrire, pas pouvoir effacer."""
    r = client.get("/api/projets", headers=ADMIN).json()
    etude = next(p for p in r if p["nom"] == "Étude B")["id"]
    assert client.put(f"/api/projets/{etude}/membres", headers=ADMIN, json={
        "genre": "utilisateur", "principal": "resp", "role": "responsable"}).status_code in (
            200, 201)
    ligne = _ligne(client, {"Remote-User": "resp"}, soeurs["b"])
    assert ligne["ecrivable"] is False and ligne["effacable"] is True
    assert "copie_par" not in ligne


@pytest.mark.parametrize("identite", [ADMIN, SAM, LECTRICE])
def test_les_champs_de_travail_de_la_requete_ne_sortent_pas(client, soeurs, identite):
    ligne = _ligne(client, identite, soeurs["b"])
    assert "_creee_par" not in ligne and "_depuis" not in ligne
