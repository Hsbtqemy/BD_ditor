"""AUTH-14 — Ctrl+Z ne traverse pas le cloisonnement des collections.

L'annulation se filtre par AGENT, et c'est voulu (cf. `docs/undo.md`). Mais les
identifiants de `regions` et de `planches` se RÉATTRIBUENT : sans `AUTOINCREMENT`, la
région créée après la suppression de la région d'identifiant le plus haut reprend cet
identifiant, dans n'importe quelle collection. L'acte journalisé désignait alors, par son
`cible_id`, un objet que son auteur n'a jamais touché — et Ctrl+Z y écrivait. Mesuré sur
`5311ccc` par une relecture croisée :

- A : un locuteur posé dans l'Incubateur, effacé par le Ctrl+Z d'une collègue qui n'y
  entre pas (200) ;
- B : le 409 de CONC-3 rendait le TEXTE de la région de l'Incubateur et le login de son
  auteur ;
- C3 : l'acte qui ne s'annulait pas bloquait la pile, indéfiniment ;
- et, lu dans le code : une personne RETIRÉE d'une collection annulait encore son dernier
  acte dedans.

Chaque test mesure la requête, la réponse ET la base, sous l'identité qui compte.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from conftest import ADMIN, make_png  # noqa: E402

IMPORTEUSE = {"Remote-User": "importeuse"}   # écrit dans Principale ET dans l'Incubateur
COLLEGUE = {"Remote-User": "collegue"}       # écrit dans Principale seulement
SECRET = "TEXTE SECRET DE L INCUBATEUR"

# La phrase que l'Atelier affiche, telle quelle (`messageErreur` lit `detail.message`).
HORS_PORTEE = "la région n'est plus à votre portée."


# --------------------------------------------------------------------------- #
# Outils
# --------------------------------------------------------------------------- #
def _sql(db_path, q, p=()):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        r = [dict(x) for x in c.execute(q, p)]
        c.commit()
        return r
    finally:
        c.close()


def _ok(r, *codes):
    assert r.status_code in codes, (r.status_code, r.text)
    return r


def _collection(client, nom):
    return _ok(client.post("/api/collections", json={"nom": nom}, headers=ADMIN),
               201).json()["id"]


def _accorder(client, cid, qui, niveau):
    _ok(client.put(f"/api/collections/{cid}/acces", headers=ADMIN,
                   json={"genre": "utilisateur", "principal": qui, "niveau": niveau}), 200)


def _retirer(client, cid, qui):
    _ok(client.delete(f"/api/collections/{cid}/acces/utilisateur/{qui}", headers=ADMIN), 204)


def _album(client, titre, cid, qui):
    return _ok(client.post("/api/albums", json={"titre": titre, "collection_id": cid},
                           headers=qui), 201).json()["id"]


def _planche(client, aid, qui):
    return _ok(client.post(f"/api/albums/{aid}/import", headers=qui,
                           files={"file": ("p.png", make_png(), "image/png")}),
               201).json()["id"]


def _region(client, pid, qui, **kw):
    corps = {"type": "bulle", "x": 0, "y": 0, "w": 9, "h": 9, **kw}
    return _ok(client.post(f"/api/planches/{pid}/regions", headers=qui, json=corps),
               201).json()["id"]


def _perso(client, nom, qui):
    return _ok(client.post("/api/personnages", json={"nom": nom}, headers=qui),
               200, 201).json()["id"]


def _texte(db_path, rid):
    r = _sql(db_path, "SELECT ocr_texte FROM regions WHERE id = ?", (rid,))
    return r[0]["ocr_texte"] if r else None


def _locuteur(db_path, rid):
    r = _sql(db_path, "SELECT personnage_id FROM bulle_locuteur WHERE region_id = ?", (rid,))
    return r[0]["personnage_id"] if r else None


def _acte(db_path, agent, type_, table, cible_id):
    """L'id du dernier acte de `agent` de cette sorte sur cette cible."""
    r = _sql(db_path, "SELECT id FROM evenement WHERE agent IS ? AND type = ? "
                      "AND cible_table = ? AND cible_id = ? ORDER BY id DESC LIMIT 1",
             (agent, type_, table, cible_id))
    assert r, (agent, type_, table, cible_id)
    return r[0]["id"]


def _annulations(db_path):
    return _sql(db_path, "SELECT COUNT(*) AS n FROM evenement WHERE type = 'annulation'")[0]["n"]


def _marques(db_path, agent):
    """Les actes que Ctrl+Z a passés pour `agent` (la trace de la propriété 4)."""
    return [r["cible_id"] for r in _sql(
        db_path, "SELECT cible_id FROM evenement WHERE type = 'abandon' "
                 "AND cible_table = 'annulation' AND agent IS ? ORDER BY id", (agent,))]


def _passe(rep, description, *, interdits=()):
    """Le refus d'un acte qui ne s'annule plus : 409, UNE phrase, et rien d'autre.

    Ce qu'il ne rend pas compte autant que ce qu'il dit : ni `conflit`, ni valeur, ni
    auteur — la région visée n'est peut-être plus lisible par qui demande."""
    assert rep.status_code == 409, rep.text
    detail = rep.json()["detail"]
    assert detail["message"] == f"Ne s'annule plus : {description} — {HORS_PORTEE}", detail
    assert set(detail) == {"message", "ecarte"}, detail
    assert detail["ecarte"]["description"] == description
    assert "conflit" not in rep.text and "valeur_actuelle" not in rep.text
    for mot in interdits:
        assert mot not in rep.text, (mot, rep.text)
    return detail["ecarte"]["evenement_id"]


# --------------------------------------------------------------------------- #
# Le décor : deux collections, et un geste ANNULABLE de la collègue dans « Garde »,
# pour prouver que la pile passe au geste d'avant au lieu de rester bloquée.
# --------------------------------------------------------------------------- #
@pytest.fixture
def decor(client, derriere_proxy, db_path):
    p, i = _collection(client, "Principale"), _collection(client, "Incubateur")
    _accorder(client, p, "importeuse", "ecriture")
    _accorder(client, i, "importeuse", "ecriture")
    _accorder(client, p, "collegue", "ecriture")
    garde = _album(client, "Garde", p, IMPORTEUSE)
    pg = _planche(client, garde, IMPORTEUSE)
    rg = _region(client, pg, IMPORTEUSE, ocr_texte="AVANT")
    e = _album(client, "Erreur", p, IMPORTEUSE)
    pe = _planche(client, e, IMPORTEUSE)
    return {"p": p, "i": i, "garde": garde, "pg": pg, "rg": rg, "e": e, "pe": pe}


def _detruire_erreur(client, decor):
    """L'album « Erreur » est détruit, et ses identifiants rendus. Par un ADMINISTRATEUR :
    la collègue y a travaillé, et depuis COL-3 l'importatrice n'efface plus seule un album
    où quelqu'un d'autre a laissé un acte — elle le demande, et c'est l'administrateur qui
    détruit. Qui détruit ne change rien à ce que ce fichier mesure : la pile de la collègue
    et les identifiants repris."""
    _ok(client.delete(f"/api/albums/{decor['e']}", headers=ADMIN), 204)


def _geste_ancien(client, decor, qui=COLLEGUE):
    """Un geste de `qui`, plus ancien, sur une région qui ne bouge pas : c'est lui que le
    Ctrl+Z suivant doit annuler une fois l'acte inannulable passé."""
    _ok(client.put(f"/api/regions/{decor['rg']}", headers=qui,
                   json={"ocr_texte": "GESTE ANCIEN"}), 200)


def _reprendre(client, decor, cible):
    """L'importatrice pose des régions dans l'Incubateur jusqu'à reprendre l'id `cible`."""
    y = _album(client, "Y", decor["i"], IMPORTEUSE)
    py = _planche(client, y, IMPORTEUSE)
    ids = []
    while cible not in ids:
        ids.append(_region(client, py, IMPORTEUSE))
        assert len(ids) < 6, (cible, ids)
    assert client.get(f"/api/albums/{y}/planches", headers=COLLEGUE).status_code == 404
    return py


# --------------------------------------------------------------------------- #
# A — écrire à travers le cloisonnement
# --------------------------------------------------------------------------- #
def test_a_un_locuteur_sur_un_identifiant_repris_ailleurs_n_est_pas_efface(
        client, db_path, decor):
    _geste_ancien(client, decor)
    r = _region(client, decor["pe"], COLLEGUE)
    _ok(client.put(f"/api/regions/{r}/locuteur", headers=COLLEGUE,
                   json={"personnage_id": _perso(client, "Haddock", COLLEGUE)}), 200)
    acte_lien = _acte(db_path, "collegue", "lien", "bulle_locuteur", r)
    acte_crea = _acte(db_path, "collegue", "creation", "regions", r)
    _detruire_erreur(client, decor)
    _reprendre(client, decor, r)
    tintin = _perso(client, "Tintin", IMPORTEUSE)
    _ok(client.put(f"/api/regions/{r}/locuteur", headers=IMPORTEUSE,
                   json={"personnage_id": tintin}), 200)
    n_annul = _annulations(db_path)

    rep = client.post("/api/undo", headers=COLLEGUE)
    assert _passe(rep, "attribution d'un locuteur", interdits=("importeuse", "Tintin")) \
        == acte_lien
    assert _locuteur(db_path, r) == tintin                  # rien n'a été écrit
    assert _marques(db_path, "collegue") == [acte_lien]     # passé, et c'est écrit
    assert _annulations(db_path) == n_annul                 # rien n'a été « annulé »

    # La pile ne reste pas bloquée : la création de la région est passée à son tour…
    rep = client.post("/api/undo", headers=COLLEGUE)
    assert _passe(rep, "création d'une région") == acte_crea
    assert _texte(db_path, r) is None and _locuteur(db_path, r) == tintin   # toujours là
    # … puis Ctrl+Z annule le geste d'avant, comme si de rien n'était.
    rep = _ok(client.post("/api/undo", headers=COLLEGUE), 200)
    assert rep.json()["region_id"] == decor["rg"]
    assert _texte(db_path, decor["rg"]) == "AVANT"


def test_a_bis_annuler_une_creation_n_efface_pas_la_region_qui_a_repris_l_identifiant(
        client, db_path, decor):
    """La même faille par l'autre bout : annuler la CRÉATION supprime la région qui porte
    l'identifiant — celle de l'Incubateur, que la garde de CONC-3 ne retient pas tant que
    personne ne l'a annotée (la planche n'est pas un champ gardé)."""
    r = _region(client, decor["pe"], COLLEGUE)
    _detruire_erreur(client, decor)
    py = _reprendre(client, decor, r)

    rep = client.post("/api/undo", headers=COLLEGUE)
    _passe(rep, "création d'une région")
    assert _sql(db_path, "SELECT planche_id FROM regions WHERE id = ?", (r,)) \
        == [{"planche_id": py}]


# --------------------------------------------------------------------------- #
# B — lire à travers le cloisonnement
# --------------------------------------------------------------------------- #
def test_b_le_refus_ne_rend_ni_le_texte_ni_l_auteur_d_une_region_illisible(
        client, db_path, decor):
    _geste_ancien(client, decor)
    r = _region(client, decor["pe"], COLLEGUE)
    _ok(client.put(f"/api/regions/{r}", headers=COLLEGUE, json={"ocr_texte": "BONJOUR"}), 200)
    _detruire_erreur(client, decor)
    _reprendre(client, decor, r)
    _ok(client.put(f"/api/regions/{r}", headers=IMPORTEUSE, json={"ocr_texte": SECRET}), 200)

    rep = client.post("/api/undo", headers=COLLEGUE)
    _passe(rep, "modification d'une région", interdits=(SECRET, "SECRET", "importeuse"))
    assert _texte(db_path, r) == SECRET


def test_b_bis_meme_sans_destruction_d_album(client, db_path, decor):
    """La région seule, supprimée par une autre, suffit à libérer l'identifiant."""
    r = _region(client, decor["pe"], COLLEGUE)
    _ok(client.put(f"/api/regions/{r}", headers=COLLEGUE, json={"ocr_texte": "BONJOUR"}), 200)
    _ok(client.delete(f"/api/regions/{r}", headers=IMPORTEUSE), 204)
    _reprendre(client, decor, r)
    _ok(client.put(f"/api/regions/{r}", headers=IMPORTEUSE, json={"ocr_texte": SECRET}), 200)

    rep = client.post("/api/undo", headers=COLLEGUE)
    _passe(rep, "modification d'une région", interdits=("SECRET", "importeuse"))
    assert _texte(db_path, r) == SECRET


def test_une_region_disparue_se_dit_comme_une_region_reprise(client, db_path, decor):
    """Sans reprise de l'identifiant, la même réponse : sinon la différence entre les deux
    apprendrait à la collègue qu'une région qu'elle ne lit pas porte désormais ce numéro.
    Sur 5311ccc : 200 « Annulé », pour un geste qui ne défaisait rien."""
    r = _region(client, decor["pe"], COLLEGUE)
    _ok(client.put(f"/api/regions/{r}/locuteur", headers=COLLEGUE,
                   json={"personnage_id": _perso(client, "Haddock", COLLEGUE)}), 200)
    _detruire_erreur(client, decor)
    n = _sql(db_path, "SELECT COUNT(*) AS n FROM evenement")[0]["n"]

    _passe(client.post("/api/undo", headers=COLLEGUE), "attribution d'un locuteur")
    assert _sql(db_path, "SELECT COUNT(*) AS n FROM evenement")[0]["n"] == n + 1   # la trace
    assert _sql(db_path, "SELECT id FROM regions WHERE id = ?", (r,)) == []


# --------------------------------------------------------------------------- #
# C3 — un acte qui ne s'annule plus ne bloque plus la pile
# --------------------------------------------------------------------------- #
def test_c3_sa_propre_suppression_sur_un_identifiant_repris_ne_bloque_plus(
        client, db_path, decor):
    _geste_ancien(client, decor)
    r = _region(client, decor["pe"], COLLEGUE)
    acte_crea = _acte(db_path, "collegue", "creation", "regions", r)
    _ok(client.delete(f"/api/regions/{r}", headers=COLLEGUE), 204)
    acte = _acte(db_path, "collegue", "suppression", "regions", r)
    py = _reprendre(client, decor, r)
    _ok(client.put(f"/api/regions/{r}", headers=IMPORTEUSE, json={"ocr_texte": SECRET}), 200)
    assert client.get("/api/undo/prochain", headers=COLLEGUE).json()["evenement_id"] == acte

    rep = client.post("/api/undo", headers=COLLEGUE)
    assert _passe(rep, "suppression d'une région", interdits=("SECRET",)) == acte
    assert _sql(db_path, "SELECT planche_id, ocr_texte FROM regions WHERE id = ?", (r,)) \
        == [{"planche_id": py, "ocr_texte": SECRET}]
    # L'aperçu et le geste suivant ont passé l'acte : plus jamais le même 409.
    assert client.get("/api/undo/prochain", headers=COLLEGUE).json()["evenement_id"] \
        == acte_crea
    assert _passe(client.post("/api/undo", headers=COLLEGUE), "création d'une région") \
        == acte_crea
    rep = _ok(client.post("/api/undo", headers=COLLEGUE), 200)
    assert rep.json()["region_id"] == decor["rg"] and _texte(db_path, decor["rg"]) == "AVANT"
    assert _marques(db_path, "collegue") == [acte, acte_crea]
    assert _texte(db_path, r) == SECRET


# --------------------------------------------------------------------------- #
# Une personne RETIRÉE d'une collection, ou rétrogradée en lecture
# --------------------------------------------------------------------------- #
@pytest.fixture
def retiree(client, decor):
    """Écrivait dans Principale, écrit encore dans l'Incubateur : elle passe le plancher
    « écrire quelque part » de la route, qui ne dit pas OÙ."""
    _accorder(client, decor["p"], "retiree", "ecriture")
    _accorder(client, decor["i"], "retiree", "ecriture")
    return {"Remote-User": "retiree"}


def test_retiree_n_annule_plus_et_ne_lit_pas_ce_qui_a_change(client, db_path, decor, retiree):
    _ok(client.put(f"/api/regions/{decor['rg']}", headers=retiree,
                   json={"ocr_texte": "DE RETIREE"}), 200)
    _ok(client.put(f"/api/regions/{decor['rg']}", headers=IMPORTEUSE,
                   json={"ocr_texte": SECRET}), 200)
    _retirer(client, decor["p"], "retiree")
    assert client.get(f"/api/regions/{decor['rg']}/annotation",
                      headers=retiree).status_code == 404       # elle ne lit plus

    rep = client.post("/api/undo", headers=retiree)
    _passe(rep, "modification d'une région", interdits=("SECRET", "importeuse"))
    assert _texte(db_path, decor["rg"]) == SECRET


def test_retiree_n_ecrit_plus_par_ctrl_z(client, db_path, decor, retiree):
    """Sans conflit à lever, le Ctrl+Z d'avant ÉCRIVAIT : 200, locuteur retiré."""
    perso = _perso(client, "Milou", retiree)
    _ok(client.put(f"/api/regions/{decor['rg']}/locuteur", headers=retiree,
                   json={"personnage_id": perso}), 200)
    _retirer(client, decor["p"], "retiree")

    _passe(client.post("/api/undo", headers=retiree), "attribution d'un locuteur")
    assert _locuteur(db_path, decor["rg"]) == perso


def test_retrogradee_en_lecture_ne_retablit_pas_ce_qu_elle_a_supprime(
        client, db_path, decor, retiree):
    """Rétrogradée en lecture : elle LIT la planche, elle n'y écrit plus — l'annulation
    d'une suppression se garde sur la planche où la région reviendrait."""
    r = _region(client, decor["pg"], retiree)
    _ok(client.delete(f"/api/regions/{r}", headers=retiree), 204)
    _accorder(client, decor["p"], "retiree", "lecture")
    assert client.get(f"/api/planches/{decor['pg']}/regions",
                      headers=retiree).status_code == 200

    _passe(client.post("/api/undo", headers=retiree), "suppression d'une région")
    assert _sql(db_path, "SELECT id FROM regions WHERE id = ?", (r,)) == []


def test_retrogradee_en_lecture_n_annule_pas_un_geste_sur_une_region_qu_elle_lit(
        client, db_path, decor, retiree):
    """La garde porte sur l'ÉCRITURE de la région, pas sur sa lecture : la région est sous
    ses yeux, et le Ctrl+Z d'avant y écrivait encore (200, locuteur retiré)."""
    perso = _perso(client, "Nestor", retiree)
    _ok(client.put(f"/api/regions/{decor['rg']}/locuteur", headers=retiree,
                   json={"personnage_id": perso}), 200)
    _accorder(client, decor["p"], "retiree", "lecture")
    assert client.get(f"/api/regions/{decor['rg']}/locuteur",
                      headers=retiree).status_code == 200      # elle LIT la région

    _passe(client.post("/api/undo", headers=retiree), "attribution d'un locuteur")
    assert _locuteur(db_path, decor["rg"]) == perso


# --------------------------------------------------------------------------- #
# Un compte COLLECTIF, un ADMINISTRATEUR
# --------------------------------------------------------------------------- #
def test_compte_collectif_meme_regle_et_borne_inchangee(client, db_path, decor):
    atelier = {"Remote-User": "atelier"}
    _accorder(client, decor["p"], "atelier", "ecriture")
    client.get("/api/moi", headers=atelier)
    _ok(client.patch("/api/comptes/atelier/nature", json={"nature": "collectif"},
                     headers=ADMIN), 200)
    r = _region(client, decor["pe"], atelier)
    _ok(client.put(f"/api/regions/{r}/locuteur", headers=atelier,
                   json={"personnage_id": _perso(client, "Castafiore", atelier)}), 200)
    _detruire_erreur(client, decor)
    _reprendre(client, decor, r)
    tintin = _perso(client, "Tintin", IMPORTEUSE)
    _ok(client.put(f"/api/regions/{r}/locuteur", headers=IMPORTEUSE,
                   json={"personnage_id": tintin}), 200)

    _passe(client.post("/api/undo", headers=atelier), "attribution d'un locuteur",
           interdits=("importeuse",))
    assert _locuteur(db_path, r) == tintin
    # La borne de cinq minutes reste ce qu'elle était : passé ce délai, rien.
    _sql(db_path, "UPDATE evenement SET date = datetime(date, '-10 minutes')")
    rep = client.post("/api/undo", headers=atelier)
    assert rep.status_code == 404 and "5 dernières minutes" in rep.json()["detail"]


def test_administrateur_n_annule_pas_sur_un_objet_qui_n_est_plus_le_sien(
        client, db_path, decor):
    """L'administrateur ÉCRIT dans l'Incubateur : la garde d'accès le laisse passer. Ce qui
    l'arrête est l'autre propriété — la région n'est plus celle sur laquelle il a agi."""
    r = _region(client, decor["pe"], ADMIN)
    _ok(client.put(f"/api/regions/{r}", headers=ADMIN, json={"ocr_texte": "DE L ADMIN"}), 200)
    _detruire_erreur(client, decor)
    _reprendre(client, decor, r)
    _ok(client.put(f"/api/regions/{r}", headers=IMPORTEUSE, json={"ocr_texte": SECRET}), 200)

    _passe(client.post("/api/undo", headers=ADMIN), "modification d'une région")
    assert _texte(db_path, r) == SECRET


def test_une_region_nee_sans_evenement_de_creation_se_reconnait_a_sa_planche(
        client, db_path, decor):
    """La segmentation lancée à l'import ShareDocs crée des régions SANS les journaliser :
    le témoin « recréée depuis » ne voit rien. Le second témoin — la planche où vivait la
    région au moment de l'acte — prend le relais. L'importatrice écrit des deux côtés :
    seule l'identité peut l'arrêter. L'insertion brute joue ce chemin d'import."""
    r = _region(client, decor["pe"], IMPORTEUSE)
    _ok(client.put(f"/api/regions/{r}", headers=IMPORTEUSE, json={"ocr_texte": "ICI"}), 200)
    _ok(client.delete(f"/api/regions/{r}", headers=IMPORTEUSE), 204)
    py = _planche(client, _album(client, "Y", decor["i"], IMPORTEUSE), IMPORTEUSE)
    _sql(db_path, "INSERT INTO regions (id, planche_id, type, x, y, w, h, ocr_texte) "
                  "VALUES (?, ?, 'bulle', 0, 0, 9, 9, ?)", (r, py, SECRET))

    _passe(client.post("/api/undo", headers=IMPORTEUSE), "suppression d'une région")
    _passe(client.post("/api/undo", headers=IMPORTEUSE), "modification d'une région")
    assert _texte(db_path, r) == SECRET


# --------------------------------------------------------------------------- #
# Rétablir une suppression : la planche et le parent doivent être les MÊMES
# --------------------------------------------------------------------------- #
def test_retablir_dans_une_planche_qui_a_repris_l_identifiant_est_refuse(
        client, db_path, decor):
    """L'importatrice écrit partout : seule l'identité de la planche l'arrête. L'album
    qui porte aujourd'hui cette planche est né APRÈS l'acte — ce n'est pas la même.

    Le journal est vieilli d'une minute : les dates sont à la seconde, et un test va plus
    vite qu'une personne. Dans la même seconde, la garde ne voit rien (résiduel écrit)."""
    s = _region(client, decor["pe"], IMPORTEUSE)
    _ok(client.delete(f"/api/regions/{s}", headers=IMPORTEUSE), 204)
    _detruire_erreur(client, decor)
    _sql(db_path, "UPDATE evenement SET date = datetime(date, '-1 minutes')")
    y = _album(client, "Y", decor["i"], IMPORTEUSE)
    assert _planche(client, y, IMPORTEUSE) == decor["pe"]     # l'identifiant est repris

    _passe(client.post("/api/undo", headers=IMPORTEUSE), "suppression d'une région")
    assert _sql(db_path, "SELECT id FROM regions WHERE id = ?", (s,)) == []


def test_retablir_sous_un_parent_qui_a_repris_l_identifiant_est_refuse(
        client, db_path, decor):
    """La bulle reviendrait dans SA planche, que la collègue écrit — mais sous une case
    de l'Incubateur, qui a repris l'identifiant de l'ancien parent."""
    c = _region(client, decor["pe"], COLLEGUE, type="case")
    b = _region(client, decor["pe"], COLLEGUE, parent_id=c)
    _ok(client.delete(f"/api/regions/{b}", headers=COLLEGUE), 204)
    _ok(client.delete(f"/api/regions/{c}", headers=IMPORTEUSE), 204)
    y = _album(client, "Y", decor["i"], IMPORTEUSE)
    assert _region(client, _planche(client, y, IMPORTEUSE), IMPORTEUSE, type="case") == c

    _passe(client.post("/api/undo", headers=COLLEGUE), "suppression d'une région")
    assert _sql(db_path, "SELECT id FROM regions WHERE id = ?", (b,)) == []


def test_un_enfant_repris_seul_passe_aussi(client, db_path, decor):
    """La réattribution séquentielle reprend la RACINE d'abord ; un enfant n'est repris
    seul que lorsqu'une autre annulation rétablit son identifiant. Le rétablissement ne
    doit pas alors tomber sur un 409 qui bloquerait la pile : il est passé, comme le reste."""
    c = _region(client, decor["pe"], COLLEGUE, type="case")
    py = _planche(client, _album(client, "Y", decor["i"], IMPORTEUSE), IMPORTEUSE)
    x = _region(client, py, IMPORTEUSE)
    _ok(client.delete(f"/api/regions/{x}", headers=IMPORTEUSE), 204)
    b = _region(client, decor["pe"], COLLEGUE, parent_id=c)
    assert b == x                                         # l'enfant a pris l'id libéré
    _ok(client.delete(f"/api/regions/{c}", headers=COLLEGUE), 204)        # emporte b
    _ok(client.post("/api/undo", headers=IMPORTEUSE), 200)                # x revient
    assert _sql(db_path, "SELECT planche_id FROM regions WHERE id = ?", (x,))         == [{"planche_id": py}]

    _passe(client.post("/api/undo", headers=COLLEGUE), "suppression d'une région")
    assert _sql(db_path, "SELECT id FROM regions WHERE id = ?", (c,)) == []
    assert _sql(db_path, "SELECT planche_id FROM regions WHERE id = ?", (x,))         == [{"planche_id": py}]


# --------------------------------------------------------------------------- #
# Ce qui ne change pas
# --------------------------------------------------------------------------- #
def test_annuler_sa_suppression_la_retablit_toujours(client, db_path, decor):
    r = _region(client, decor["pg"], COLLEGUE, ocr_texte="ICI")
    _ok(client.delete(f"/api/regions/{r}", headers=COLLEGUE), 204)
    rep = _ok(client.post("/api/undo", headers=COLLEGUE), 200)
    assert rep.json()["acte"] == "suppression" and rep.json()["region_id"] == r
    assert _sql(db_path, "SELECT planche_id, ocr_texte FROM regions WHERE id = ?", (r,)) \
        == [{"planche_id": decor["pg"], "ocr_texte": "ICI"}]
    assert _marques(db_path, "collegue") == []


def test_un_conflit_sur_une_region_lisible_reste_le_conflit_de_conc_3(
        client, db_path, decor):
    """La collègue LIT la région : le 409 nommé est inchangé — valeur et auteur compris —,
    rien n'est passé, et la pile reste sur cet acte comme avant."""
    _geste_ancien(client, decor)
    _ok(client.put(f"/api/regions/{decor['rg']}", headers=IMPORTEUSE,
                   json={"ocr_texte": "PAR L IMPORTATRICE"}), 200)
    for _ in range(2):
        rep = client.post("/api/undo", headers=COLLEGUE)
        assert rep.status_code == 409, rep.text
        conflit = rep.json()["detail"]["conflit"]
        assert conflit["valeur_actuelle"] == "PAR L IMPORTATRICE"
        assert conflit["auteur"]["login"] == "importeuse"
    assert _marques(db_path, "collegue") == []
    assert _texte(db_path, decor["rg"]) == "PAR L IMPORTATRICE"


def test_la_trace_du_passage_ne_part_pas_au_depot(client, db_path, decor):
    """La marque est un acte du journal : elle doit être RETENUE, comme l'administration,
    et non publiée — elle n'a rien changé au corpus."""
    import _commun

    def publies():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        try:
            return [dict(x) for x in _commun.evenements_publiables(c)]
        finally:
            c.close()

    r = _region(client, decor["pe"], COLLEGUE)
    _ok(client.put(f"/api/regions/{r}", headers=COLLEGUE, json={"ocr_texte": "BONJOUR"}), 200)
    _detruire_erreur(client, decor)
    _reprendre(client, decor, r)
    avant = publies()
    _passe(client.post("/api/undo", headers=COLLEGUE), "modification d'une région")
    assert _marques(db_path, "collegue"), "le semis : aucune marque posée"
    assert publies() == avant
    assert "annulation" in _commun.CIBLES_RETENUES


# --------------------------------------------------------------------------- #
# Relecture croisée — le PARENT d'une région (S1, préexistant)
# --------------------------------------------------------------------------- #
INCUB = {"Remote-User": "incub"}   # écrit dans l'Incubateur SEULEMENT

IRRETABLISSABLE = "l'état d'avant ne peut plus être rétabli."


def _incub(client, decor):
    _accorder(client, decor["i"], "incub", "ecriture")
    return _planche(client, _album(client, "Y", decor["i"], INCUB), INCUB)


def _parent(db_path, rid):
    return _sql(db_path, "SELECT parent_id FROM regions WHERE id = ?", (rid,))[0]["parent_id"]


def test_rendre_un_parent_repris_ailleurs_est_refuse(client, db_path, decor):
    """L'inverse d'une modification remettait `parent_id` sans rien valider : la bulle de la
    collègue devenait l'enfant d'une case de l'Incubateur — puis la suppression de cette
    case l'emportait, et son rétablissement la recréait, à travers le cloisonnement."""
    c2 = _region(client, decor["pe"], COLLEGUE, type="case")
    b = _region(client, decor["pe"], COLLEGUE)
    c1 = _region(client, decor["pe"], COLLEGUE, type="case")      # identifiant le plus haut
    _ok(client.put(f"/api/regions/{b}", headers=COLLEGUE, json={"parent_id": c1}), 200)
    _ok(client.put(f"/api/regions/{b}", headers=COLLEGUE, json={"parent_id": c2}), 200)
    _ok(client.delete(f"/api/regions/{c1}", headers=IMPORTEUSE), 204)
    assert _region(client, _incub(client, decor), INCUB, type="case") == c1

    _passe(client.post("/api/undo", headers=COLLEGUE), "modification d'une région")
    assert _parent(db_path, b) == c2


def test_retablir_un_sous_arbre_juge_la_planche_de_chaque_noeud(client, db_path, decor):
    """Un instantané dont un enfant vit dans une AUTRE planche (une base qu'une annulation
    d'avant ce correctif a pu laisser ainsi) : la racine est chez incub, l'enfant dans
    Principale. Juger la racine seule laissait incub recréer la bulle de la collègue."""
    py = _incub(client, decor)
    c = _region(client, py, INCUB, type="case")
    b = _region(client, decor["pe"], COLLEGUE, ocr_texte="DE LA COLLEGUE")
    _sql(db_path, "UPDATE regions SET parent_id = ? WHERE id = ?", (c, b))
    _ok(client.delete(f"/api/regions/{c}", headers=INCUB), 204)
    assert _sql(db_path, "SELECT id FROM regions WHERE id = ?", (b,)) == []   # emportée

    _passe(client.post("/api/undo", headers=INCUB), "suppression d'une région")
    assert _sql(db_path, "SELECT id FROM regions WHERE id IN (?, ?)", (b, c)) == []


def test_rendre_un_parent_qui_ferait_un_cycle_est_refuse(client, db_path, decor):
    """L'inverse valide le parent comme la route : même planche, et pas de cycle."""
    c = _region(client, decor["pe"], COLLEGUE, type="case")
    b = _region(client, decor["pe"], COLLEGUE, type="case", parent_id=c)
    _ok(client.put(f"/api/regions/{b}", headers=COLLEGUE, json={"parent_id": None}), 200)
    _ok(client.put(f"/api/regions/{c}", headers=IMPORTEUSE, json={"parent_id": b}), 200)

    rep = client.post("/api/undo", headers=COLLEGUE)
    assert rep.status_code == 409, rep.text
    assert rep.json()["detail"]["message"] == \
        f"Ne s'annule plus : modification d'une région — {IRRETABLISSABLE}"
    assert (_parent(db_path, b), _parent(db_path, c)) == (None, b)


def test_ce_que_l_inversion_a_commence_d_ecrire_ne_part_pas_avec_la_trace(
        client, db_path, decor, monkeypatch):
    """Le contrat de la route : la trace est VALIDÉE malgré le refus, donc ce que
    l'inversion aurait déjà écrit doit être défait avant elle — sans quoi la trace
    l'emporterait avec elle. Aucun chemin d'aujourd'hui n'écrit avant de lever (la
    validation précède l'écriture) : on fait écrire l'inversion, puis lever."""
    import undo
    _ok(client.put(f"/api/regions/{decor['rg']}", headers=COLLEGUE,
                   json={"ocr_texte": "DE LA COLLEGUE"}), 200)

    def inversion_qui_ecrit_puis_leve(conn, e):
        conn.execute("UPDATE regions SET ocr_texte = 'ECRIT PUIS DEFAIT' WHERE id = ?",
                     (e["cible_id"],))
        raise undo.Irretablissable()
    monkeypatch.setattr(undo, "_inverser", inversion_qui_ecrit_puis_leve)

    rep = client.post("/api/undo", headers=COLLEGUE)
    assert rep.json()["detail"]["message"] == \
        f"Ne s'annule plus : modification d'une région — {IRRETABLISSABLE}"
    assert _texte(db_path, decor["rg"]) == "DE LA COLLEGUE"
    assert len(_marques(db_path, "collegue")) == 1


# --------------------------------------------------------------------------- #
# Relecture croisée — une contrainte violée ne bloque plus la pile (S5, S5b)
# --------------------------------------------------------------------------- #
def test_un_personnage_supprime_depuis_ne_bloque_plus_la_pile(client, db_path, decor):
    """Rétablir le locuteur d'avant, que quelqu'un a supprimé depuis : la contrainte de clé
    étrangère refusait, et le même 409 « FOREIGN KEY constraint failed » revenait à chaque
    Ctrl+Z. L'acte est passé ; le suivant s'annule."""
    haddock = _perso(client, "Haddock", COLLEGUE)
    milou = _perso(client, "Milou", COLLEGUE)
    _ok(client.put(f"/api/regions/{decor['rg']}/locuteur", headers=COLLEGUE,
                   json={"personnage_id": haddock}), 200)
    _ok(client.put(f"/api/regions/{decor['rg']}/locuteur", headers=COLLEGUE,
                   json={"personnage_id": milou}), 200)
    acte = _acte(db_path, "collegue", "lien", "bulle_locuteur", decor["rg"])
    _ok(client.delete(f"/api/personnages/{haddock}", headers=IMPORTEUSE), 204)

    rep = client.post("/api/undo", headers=COLLEGUE)
    assert rep.status_code == 409, rep.text
    assert rep.json()["detail"] == {
        "message": f"Ne s'annule plus : attribution d'un locuteur — {IRRETABLISSABLE}",
        "ecarte": {"evenement_id": acte, "description": "attribution d'un locuteur"}}
    assert "FOREIGN" not in rep.text and _locuteur(db_path, decor["rg"]) == milou
    assert _marques(db_path, "collegue") == [acte]
    _ok(client.post("/api/undo", headers=COLLEGUE), 200)        # la pile a avancé


def test_un_ancien_parent_supprime_depuis_ne_bloque_plus_la_pile(client, db_path, decor):
    """Même chose pour le parent : rendre un parent supprimé depuis (sans reprise)."""
    _geste_ancien(client, decor)
    c1 = _region(client, decor["pe"], COLLEGUE, type="case")
    b = _region(client, decor["pe"], COLLEGUE, parent_id=c1)
    _ok(client.put(f"/api/regions/{b}", headers=COLLEGUE, json={"parent_id": None}), 200)
    _region(client, decor["pe"], IMPORTEUSE)          # c1 n'est plus le plus haut : pas de reprise
    _ok(client.delete(f"/api/regions/{c1}", headers=IMPORTEUSE), 204)

    rep = client.post("/api/undo", headers=COLLEGUE)
    assert rep.json()["detail"]["message"] == \
        f"Ne s'annule plus : modification d'une région — {IRRETABLISSABLE}"
    assert _parent(db_path, b) is None


# --------------------------------------------------------------------------- #
# Relecture croisée — le témoin « supprimée depuis » (S3)
# --------------------------------------------------------------------------- #
def _inserer_sans_evenement(db_path, rid, planche):
    """Ce que fait la segmentation lancée à l'import ShareDocs : une région, aucun acte."""
    _sql(db_path, "INSERT INTO regions (id, planche_id, type, x, y, w, h) "
                  "VALUES (?, ?, 'bulle', 0, 0, 9, 9)", (rid, planche))


def test_une_suppression_journalisee_depuis_l_acte_prouve_que_l_objet_n_est_plus(
        client, db_path, decor):
    """Région née sans événement, reprise sans événement dans un album de l'Incubateur
    PLUS ANCIEN que l'acte : aucun des trois témoins ne voyait rien. La suppression
    journalisée entre-temps, elle, prouve que l'objet de l'acte n'existe plus."""
    py = _incub(client, decor)
    _sql(db_path, "UPDATE albums SET date_import = datetime(date_import, '-10 minutes')")
    rid = _sql(db_path, "SELECT COALESCE(MAX(id), 0) + 1 AS n FROM regions")[0]["n"]
    _inserer_sans_evenement(db_path, rid, decor["pe"])
    _ok(client.put(f"/api/regions/{rid}/locuteur", headers=IMPORTEUSE,
                   json={"personnage_id": _perso(client, "Dupond", IMPORTEUSE)}), 200)
    _ok(client.delete(f"/api/regions/{rid}", headers=COLLEGUE), 204)
    _inserer_sans_evenement(db_path, rid, py)
    p2 = _perso(client, "Dupont", INCUB)
    _ok(client.put(f"/api/regions/{rid}/locuteur", headers=INCUB, json={"personnage_id": p2}), 200)

    _passe(client.post("/api/undo", headers=IMPORTEUSE), "attribution d'un locuteur")
    assert _locuteur(db_path, rid) == p2


def test_une_suppression_annulee_depuis_ne_compte_pas(client, db_path, decor):
    """La région supprimée PUIS rétablie est la même : son rétablissement l'a rendue, sous
    le même identifiant. Le témoin ne doit pas refuser l'annulation qui suit."""
    _ok(client.put(f"/api/regions/{decor['rg']}", headers=COLLEGUE,
                   json={"ocr_texte": "DE LA COLLEGUE"}), 200)
    _ok(client.delete(f"/api/regions/{decor['rg']}", headers=IMPORTEUSE), 204)
    _ok(client.post("/api/undo", headers=IMPORTEUSE), 200)            # rétablie

    _ok(client.post("/api/undo", headers=COLLEGUE), 200)
    assert _texte(db_path, decor["rg"]) == "AVANT"


def test_un_parent_supprime_puis_repris_sans_evenement_n_est_plus_le_meme(
        client, db_path, decor):
    """Même planche, aucun événement de création : seul le témoin « supprimée depuis »
    reconnaît que l'ancien parent n'est plus là — pour une modification…"""
    c2 = _region(client, decor["pe"], COLLEGUE, type="case")
    c1 = _region(client, decor["pe"], COLLEGUE, type="case")
    b = _region(client, decor["pe"], COLLEGUE, parent_id=c1)
    _ok(client.put(f"/api/regions/{b}", headers=COLLEGUE, json={"parent_id": c2}), 200)
    _region(client, decor["pe"], IMPORTEUSE)
    _ok(client.delete(f"/api/regions/{c1}", headers=IMPORTEUSE), 204)
    _inserer_sans_evenement(db_path, c1, decor["pe"])

    _passe(client.post("/api/undo", headers=COLLEGUE), "modification d'une région")
    assert _parent(db_path, b) == c2


def test_retablir_sous_un_parent_supprime_puis_repris_sans_evenement_est_refuse(
        client, db_path, decor):
    """… et pour le rétablissement d'une suppression."""
    c = _region(client, decor["pe"], COLLEGUE, type="case")
    b = _region(client, decor["pe"], COLLEGUE, parent_id=c)
    _region(client, decor["pe"], IMPORTEUSE)
    _ok(client.delete(f"/api/regions/{b}", headers=COLLEGUE), 204)
    _ok(client.delete(f"/api/regions/{c}", headers=IMPORTEUSE), 204)
    _inserer_sans_evenement(db_path, c, decor["pe"])

    _passe(client.post("/api/undo", headers=COLLEGUE), "suppression d'une région")
    assert _sql(db_path, "SELECT id FROM regions WHERE id = ?", (b,)) == []


def test_une_region_emportee_par_la_suppression_de_son_parent_n_est_plus_la_meme(
        client, db_path, decor):
    """La suppression d'une case emporte ses bulles : le journal n'a d'événement que pour
    la case, la bulle n'est que dans son instantané. Reprise sans événement dans la même
    planche, la bulle n'est plus celle de l'acte."""
    c = _region(client, decor["pe"], COLLEGUE, type="case")
    b = _region(client, decor["pe"], COLLEGUE, parent_id=c)
    _ok(client.put(f"/api/regions/{b}", headers=COLLEGUE, json={"ocr_texte": "BONJOUR"}), 200)
    _ok(client.delete(f"/api/regions/{c}", headers=IMPORTEUSE), 204)       # emporte b
    _inserer_sans_evenement(db_path, b, decor["pe"])
    _sql(db_path, "UPDATE regions SET ocr_texte = 'AUTRE OBJET' WHERE id = ?", (b,))

    _passe(client.post("/api/undo", headers=COLLEGUE), "modification d'une région")
    assert _texte(db_path, b) == "AUTRE OBJET"


# --------------------------------------------------------------------------- #
# Relecture croisée — la trace n'est pas du travail (S6)
# --------------------------------------------------------------------------- #
def test_la_trace_ne_compte_pas_comme_un_acte_laisse(client, db_path, decor):
    """« Comptes et groupes » compte les actes d'un login pour dire ce qu'une suppression
    du compte orphelinerait. Un Ctrl+Z passé n'a rien produit."""
    import comptes

    def actes():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        try:
            return comptes.traces(c)[0].get("collegue")
        finally:
            c.close()

    _region(client, decor["pe"], COLLEGUE)
    _detruire_erreur(client, decor)
    avant = actes()
    _passe(client.post("/api/undo", headers=COLLEGUE), "création d'une région")
    assert _marques(db_path, "collegue"), "le semis : aucune trace posée"
    assert actes() == avant == 1


# --------------------------------------------------------------------------- #
# Relecture croisée — un témoin chacun (S8, S9, S10). La disparition se fait SANS
# événement, comme une re-passe ML qui remplace les régions machine : sinon le témoin
# « supprimée depuis » répondrait à la place de celui qu'on éprouve.
# --------------------------------------------------------------------------- #
def _effacer_sans_evenement(db_path, rid):
    _sql(db_path, "DELETE FROM regions WHERE id = ?", (rid,))


def test_retablir_sous_un_parent_repris_dans_une_autre_planche_est_refuse(
        client, db_path, decor):
    """Seul le témoin « parent dans la même planche » voit ce cas (S8)."""
    py = _incub(client, decor)
    c = _region(client, decor["pe"], COLLEGUE, type="case")
    b = _region(client, decor["pe"], COLLEGUE, parent_id=c, ocr_texte="BULLE")
    _ok(client.delete(f"/api/regions/{b}", headers=COLLEGUE), 204)
    _effacer_sans_evenement(db_path, c)
    _inserer_sans_evenement(db_path, c, py)

    _passe(client.post("/api/undo", headers=COLLEGUE), "suppression d'une région")
    assert _sql(db_path, "SELECT id FROM regions WHERE id = ?", (b,)) == []


def test_une_region_reprise_dans_un_album_ne_apres_l_acte_n_est_plus_la_meme(
        client, db_path, decor):
    """Seul le témoin « album né après l'acte » voit ce cas, pour un acte autre qu'une
    suppression (S9)."""
    rid = _sql(db_path, "SELECT COALESCE(MAX(id), 0) + 1 AS n FROM regions")[0]["n"]
    _inserer_sans_evenement(db_path, rid, decor["pe"])
    _ok(client.put(f"/api/regions/{rid}/locuteur", headers=IMPORTEUSE,
                   json={"personnage_id": _perso(client, "Dupond", IMPORTEUSE)}), 200)
    _effacer_sans_evenement(db_path, rid)
    _sql(db_path, "UPDATE evenement SET date = datetime(date, '-1 minutes')")
    py = _incub(client, decor)                                       # album né APRÈS l'acte
    _inserer_sans_evenement(db_path, rid, py)
    p2 = _perso(client, "Dupont", INCUB)
    _ok(client.put(f"/api/regions/{rid}/locuteur", headers=INCUB, json={"personnage_id": p2}), 200)

    _passe(client.post("/api/undo", headers=IMPORTEUSE), "attribution d'un locuteur")
    assert _locuteur(db_path, rid) == p2


def test_un_identifiant_deja_servi_puis_repris_s_annule_sur_le_nouvel_objet(
        client, db_path, decor):
    """Le témoin « planche au moment de l'acte » s'arrête à la dernière suppression : avant
    elle, le journal parle d'un AUTRE objet. Sans cet arrêt, il comparait la planche de
    l'ancien à celle du nouveau, et refusait un Ctrl+Z légitime (S10)."""
    vieux = _region(client, decor["pg"], COLLEGUE)
    _ok(client.delete(f"/api/regions/{vieux}", headers=COLLEGUE), 204)
    _ok(client.post("/api/undo", headers=COLLEGUE), 200)            # rétablie…
    _ok(client.delete(f"/api/regions/{vieux}", headers=IMPORTEUSE), 204)   # … puis supprimée
    _inserer_sans_evenement(db_path, vieux, decor["pe"])
    p = _perso(client, "Tournesol", COLLEGUE)
    _ok(client.put(f"/api/regions/{vieux}/locuteur", headers=COLLEGUE,
                   json={"personnage_id": p}), 200)

    rep = _ok(client.post("/api/undo", headers=COLLEGUE), 200)
    assert rep.json()["acte"] == "lien" and _locuteur(db_path, vieux) is None


# --------------------------------------------------------------------------- #
# Relecture croisée — un PERSONNAGE repris (S2). Ses identifiants se réattribuent
# comme ceux des régions, et l'acte n'en garde que l'identifiant.
# --------------------------------------------------------------------------- #
def _personnage_repris(client, db_path, decor):
    """La collègue change le locuteur de Haddock à Milou ; Haddock est supprimé, et
    l'Incubateur crée un personnage qui reprend son identifiant."""
    r = _region(client, decor["pe"], COLLEGUE)
    milou = _perso(client, "Milou", COLLEGUE)
    haddock = _perso(client, "Haddock", COLLEGUE)                 # identifiant le plus haut
    _ok(client.put(f"/api/regions/{r}/locuteur", headers=COLLEGUE,
                   json={"personnage_id": haddock}), 200)
    _ok(client.put(f"/api/regions/{r}/locuteur", headers=COLLEGUE,
                   json={"personnage_id": milou}), 200)
    _ok(client.delete(f"/api/personnages/{haddock}", headers=IMPORTEUSE), 204)
    py = _incub(client, decor)
    secret = _perso(client, "PERSONNAGE SECRET", INCUB)
    assert secret == haddock
    _ok(client.put(f"/api/regions/{_region(client, py, INCUB)}/locuteur", headers=INCUB,
                   json={"personnage_id": secret}), 200)
    return r, milou, secret


def _noms_vus(client, qui):
    return {p["nom"] for p in client.get("/api/personnages", headers=qui).json()}


def test_ctrl_z_ne_pose_pas_un_personnage_que_l_agent_ne_voit_pas(client, db_path, decor):
    """Le personnage repris n'apparaît que dans l'Incubateur : la collègue ne le voit pas.
    Le reposer l'attribuait à sa bulle — et le lui montrait du même coup (S2)."""
    r, milou, secret = _personnage_repris(client, db_path, decor)
    assert "PERSONNAGE SECRET" not in _noms_vus(client, COLLEGUE)

    rep = client.post("/api/undo", headers=COLLEGUE)
    assert rep.status_code == 409, rep.text
    assert rep.json()["detail"]["message"] == \
        f"Ne s'annule plus : attribution d'un locuteur — {IRRETABLISSABLE}"
    assert "SECRET" not in rep.text
    assert _locuteur(db_path, r) == milou
    assert "PERSONNAGE SECRET" not in _noms_vus(client, COLLEGUE)


def test_ctrl_z_ne_pose_pas_un_personnage_cree_apres_l_acte(client, db_path, decor):
    """Visible cette fois (il apparaît aussi dans Principale) : seule sa date de création,
    postérieure à l'acte, dit que ce n'est plus Haddock. Journal et albums sont vieillis
    d'une minute ensemble : les dates sont à la seconde."""
    r, milou, secret = _personnage_repris(client, db_path, decor)
    _ok(client.put(f"/api/regions/{decor['rg']}/locuteur", headers=IMPORTEUSE,
                   json={"personnage_id": secret}), 200)
    assert "PERSONNAGE SECRET" in _noms_vus(client, COLLEGUE)
    _sql(db_path, "UPDATE evenement SET date = datetime(date, '-1 minutes')")
    _sql(db_path, "UPDATE albums SET date_import = datetime(date_import, '-1 minutes')")

    rep = client.post("/api/undo", headers=COLLEGUE)
    assert rep.status_code == 409, rep.text
    assert rep.json()["detail"]["message"] == \
        f"Ne s'annule plus : attribution d'un locuteur — {IRRETABLISSABLE}"
    assert _locuteur(db_path, r) == milou
