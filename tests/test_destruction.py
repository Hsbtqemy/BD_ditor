"""AUTH-10 — supprimer n'est pas sortir.

Un album vit dans plusieurs collections, et l'annoter ne demande d'écrire que dans UNE :
c'est voulu, le travail fait dans une étude se voit dans l'autre. Le DÉTRUIRE passait par
le même accesseur, donc par la même union — un compte qui n'écrivait que dans l'incubateur
effaçait l'album du corpus principal, qu'il ne lisait même pas. Reproduit le 2026-10-08.

La règle (Hugo, 2026-10-08) : détruire un album, ou l'une de ses planches, demande d'écrire
dans TOUTES les collections où il vit ; sortir l'album de sa collection reste permis à qui y
écrit. Ces tests jouent le geste sous CHAQUE identité, et regardent ensuite ce que voient
les AUTRES — un code de retour seul ne dit pas si l'album a survécu.
"""
import ast
import re
import sqlite3
from pathlib import Path

import pytest

import autorisation
from conftest import ADMIN, make_png

RACINE = Path(__file__).resolve().parent.parent

STAGIAIRE = {"Remote-User": "stagiaire"}        # écrit dans l'incubateur, ne lit rien d'autre
PASSEUSE = {"Remote-User": "passeuse"}          # écrit dans les deux
MIXTE = {"Remote-User": "mixte"}                # écrit dans l'incubateur, LIT la principale
LECTRICE = {"Remote-User": "lectrice"}          # lit la principale, n'écrit nulle part


def _collection(client, nom):
    return client.post("/api/collections", json={"nom": nom}, headers=ADMIN).json()["id"]


def _album(client, titre, cid):
    return client.post("/api/albums", json={"titre": titre, "collection_id": cid},
                       headers=ADMIN).json()["id"]


def _planche(client, album_id):
    r = client.post(f"/api/albums/{album_id}/import", headers=ADMIN,
                    files={"file": ("p.png", make_png(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _ranger(client, album_id, cid):
    r = client.put(f"/api/albums/{album_id}/collections/{cid}", headers=ADMIN)
    assert r.status_code == 201, r.text


def _accorder(client, cid, principal, niveau, genre="utilisateur"):
    r = client.put(f"/api/collections/{cid}/acces", headers=ADMIN,
                   json={"genre": genre, "principal": principal, "niveau": niveau})
    assert r.status_code == 200, r.text


@pytest.fixture
def decor(client, derriere_proxy):
    """Deux collections, un album rangé dans les DEUX (une planche), un autre dans
    l'incubateur seul (une planche) — et quatre comptes qui n'y ont pas les mêmes droits.

    Les identifiants sont DÉCROISÉS exprès, et c'est affirmé : la planche de l'album partagé
    porte l'id de l'album seul, et l'inverse. Alignés (album 1 ↔ planche 1), une garde de
    `delete_planche` qui interrogerait l'id de la PLANCHE au lieu de celui de son album
    passait toute la suite — trouvé par la relecture croisée, en faisant survivre le mutant.
    """
    principale, incubateur = _collection(client, "Principale"), _collection(client, "Incubateur")
    seul = _album(client, "Seul", incubateur)
    partage = _album(client, "Partagé", principale)
    planche_partagee = _planche(client, partage)
    planche_seule = _planche(client, seul)
    assert (planche_partagee, planche_seule) == (seul, partage), "les ids doivent se croiser"
    _ranger(client, partage, incubateur)
    for cid, qui, niveau in ((incubateur, "stagiaire", "ecriture"),
                             (incubateur, "passeuse", "ecriture"),
                             (principale, "passeuse", "ecriture"),
                             (incubateur, "mixte", "ecriture"),
                             (principale, "mixte", "lecture"),
                             (principale, "lectrice", "lecture")):
        _accorder(client, cid, qui, niveau)
    return {"principale": principale, "incubateur": incubateur, "partage": partage,
            "seul": seul, "planche_partagee": planche_partagee,
            "planche_seule": planche_seule}


def _albums(client, qui):
    return {a["id"]: a for a in client.get("/api/albums", headers=qui).json()}


def _planches(client, album_id, qui=ADMIN):
    return [p["id"] for p in client.get(f"/api/albums/{album_id}/planches", headers=qui).json()]


# ── le constat, gardé ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("qui", [STAGIAIRE, MIXTE], ids=["n-y-lit-rien", "y-lit-seulement"])
def test_ecrire_dans_une_collection_ne_detruit_pas_l_album_des_autres(client, decor, qui):
    """Le constat du 2026-10-08. Lire l'autre collection n'y change rien : c'est d'y
    ÉCRIRE qu'il s'agit — sans le second cas, « écrire partout » pourrait se réduire en
    « voir partout » sans rien faire tomber."""
    r = client.delete(f"/api/albums/{decor['partage']}", headers=qui)
    assert r.status_code == 403, r.text
    # Le refus dit quel geste reste, et ne NOMME pas l'autre collection.
    assert "sortir" in r.json()["detail"] and "Principale" not in r.json()["detail"]
    assert decor["partage"] in _albums(client, LECTRICE)
    assert decor["partage"] in _albums(client, ADMIN)
    assert _planches(client, decor["partage"]) == [decor["planche_partagee"]]


@pytest.mark.parametrize("qui", [STAGIAIRE, MIXTE], ids=["n-y-lit-rien", "y-lit-seulement"])
def test_ni_ses_planches_une_a_une(client, decor, qui):
    """Une planche n'a pas d'appartenance propre, donc pas de « sortir » : sans la même
    garde, elle restait le chemin par lequel on vide un album partagé."""
    r = client.delete(f"/api/planches/{decor['planche_partagee']}", headers=qui)
    assert r.status_code == 403, r.text
    assert _planches(client, decor["partage"]) == [decor["planche_partagee"]]


def test_sortir_reste_permis_et_ne_detruit_rien(client, decor):
    """Le geste qui reste à qui n'écrit que d'un côté. Il ne détruit rien — et pour LUI
    c'est un aller simple : ne voyant plus l'album, il ne peut pas l'y ranger de nouveau.
    Qui écrit des deux côtés le peut. Les documents disaient « le geste se défait » sans
    dire par qui ; ce test tient les deux moitiés de la phrase corrigée."""
    lien = f"/api/albums/{decor['partage']}/collections/{decor['incubateur']}"
    r = client.delete(lien, headers=STAGIAIRE)
    assert r.status_code == 204, r.text
    assert decor["partage"] not in _albums(client, STAGIAIRE)
    assert decor["partage"] in _albums(client, LECTRICE)
    assert _planches(client, decor["partage"]) == [decor["planche_partagee"]]
    assert client.put(lien, headers=STAGIAIRE).status_code == 404
    assert client.put(lien, headers=PASSEUSE).status_code == 201
    assert decor["partage"] in _albums(client, STAGIAIRE)


# ── ce que la règle ne doit PAS fermer ───────────────────────────────────────────────────
def test_qui_ecrit_dans_toutes_ses_collections_detruit(client, decor):
    assert client.delete(f"/api/planches/{decor['planche_partagee']}",
                         headers=PASSEUSE).status_code == 204
    assert client.delete(f"/api/albums/{decor['partage']}", headers=PASSEUSE).status_code == 204
    assert decor["partage"] not in _albums(client, ADMIN)


def test_un_album_d_une_seule_collection_se_detruit_comme_avant(client, decor):
    """La question du 2026-09-10 — qui écrit dans l'unique collection d'un album le détruit
    — n'est pas rouverte par cette règle."""
    assert client.delete(f"/api/planches/{decor['planche_seule']}",
                         headers=STAGIAIRE).status_code == 204
    assert client.delete(f"/api/albums/{decor['seul']}", headers=STAGIAIRE).status_code == 204
    assert decor["seul"] not in _albums(client, ADMIN)


def test_l_administrateur_detruit_sans_figurer_nulle_part(client, decor):
    assert client.delete(f"/api/albums/{decor['partage']}", headers=ADMIN).status_code == 204


def test_qui_n_ecrit_nulle_part_recoit_toujours_un_404(client, decor):
    """Inchangé : la garde de destruction ne passe qu'APRÈS l'accesseur gardé en écriture.
    Un 403 ici dirait à qui ne lit pas l'album qu'il existe."""
    assert client.delete(f"/api/albums/{decor['partage']}", headers=LECTRICE).status_code == 404
    assert client.delete(f"/api/albums/{decor['seul']}", headers=LECTRICE).status_code == 404
    assert client.delete(f"/api/planches/{decor['planche_seule']}",
                         headers=LECTRICE).status_code == 404


def test_en_mono_poste_rien_ne_change(client, album, planche):
    """Sans proxy, la portée est totale : il n'y a personne à qui refuser."""
    lu = client.get("/api/albums").json()[0]
    assert lu["destructible"] is True and lu["ecrivable"] is True
    assert client.delete(f"/api/planches/{planche['id']}").status_code == 204
    assert client.delete(f"/api/albums/{album['id']}").status_code == 204


# ── les mêmes droits, reçus autrement ────────────────────────────────────────────────────
def test_un_droit_recu_par_un_groupe_suit_la_meme_regle(client, derriere_proxy):
    """La portée cumule les accès du login et ceux de ses groupes : la règle doit valoir pour
    les deux. Un groupe qui n'écrit que d'un côté ne détruit pas ; des deux, il détruit."""
    membre = {"Remote-User": "membre", "Remote-Groups": "equipe"}
    a, b = _collection(client, "A"), _collection(client, "B")
    album = _album(client, "Partagé", a)
    _ranger(client, album, b)
    _accorder(client, a, "equipe", "ecriture", genre="groupe")
    assert client.delete(f"/api/albums/{album}", headers=membre).status_code == 403
    _accorder(client, b, "equipe", "ecriture", genre="groupe")
    assert _albums(client, membre)[album]["destructible"] is True
    assert client.delete(f"/api/albums/{album}", headers=membre).status_code == 204


def test_posseder_une_collection_ne_detruit_pas_l_album_des_autres(client, derriere_proxy):
    """Le sommet de l'échelle ne passe pas outre : posséder A, c'est décider de A. Seul
    l'administrateur écrit partout sans figurer nulle part."""
    a, b = _collection(client, "A"), _collection(client, "B")
    album = _album(client, "Partagé", a)
    planche = _planche(client, album)
    _ranger(client, album, b)
    _accorder(client, a, "proprio", "proprietaire")
    qui = {"Remote-User": "proprio"}
    assert client.delete(f"/api/albums/{album}", headers=qui).status_code == 403
    assert client.delete(f"/api/planches/{planche}", headers=qui).status_code == 403
    lu = _albums(client, qui)[album]
    assert (lu["ecrivable"], lu["destructible"]) == (True, False)


def test_toutes_veut_dire_toutes_et_le_refus_ne_compte_pas(client, derriere_proxy):
    """Trois collections : écrire dans deux ne suffit pas. Et le refus est le MÊME texte que
    pour un album rangé dans deux — il révèle qu'une autre collection existe (accepté par
    écrit), pas COMBIEN : un message qui compterait dirait la composition du corpus."""
    a, b, c = (_collection(client, n) for n in ("A", "B", "C"))
    a_trois = _album(client, "À trois", a)
    _ranger(client, a_trois, b)
    _ranger(client, a_trois, c)
    a_deux = _album(client, "À deux", a)
    _ranger(client, a_deux, c)
    _accorder(client, a, "deux", "ecriture")
    _accorder(client, b, "deux", "ecriture")
    qui = {"Remote-User": "deux"}
    refus_trois = client.delete(f"/api/albums/{a_trois}", headers=qui)
    refus_deux = client.delete(f"/api/albums/{a_deux}", headers=qui)
    assert refus_trois.status_code == refus_deux.status_code == 403
    assert refus_trois.json() == refus_deux.json()
    _accorder(client, c, "deux", "ecriture")
    assert client.delete(f"/api/albums/{a_trois}", headers=qui).status_code == 204


# ── ce que le serveur DIT, pour que l'écran ne propose que ce qui aboutira ───────────────
def test_la_liste_des_albums_dit_ce_qu_on_peut_y_faire(client, decor):
    """`destructible` et `ecrivable`, album par album et identité par identité, contre une
    table écrite à la main. Les gestes eux-mêmes sont joués par les tests du dessus ; ce
    que celui-ci garde, c'est que la liste ANNONCE la même chose.

    Les deux champs vont ensemble : « non destructible » a deux causes, et l'écran n'a un
    geste à offrir — sortir — que si l'on écrit dans l'album. Une lectrice reçoit donc
    (False, False), et sa ligne ne porte rien."""
    attendu = {  # (ecrivable, destructible)
        "stagiaire": (STAGIAIRE, {decor["partage"]: (True, False), decor["seul"]: (True, True)}),
        "passeuse": (PASSEUSE, {decor["partage"]: (True, True), decor["seul"]: (True, True)}),
        "mixte": (MIXTE, {decor["partage"]: (True, False), decor["seul"]: (True, True)}),
        "lectrice": (LECTRICE, {decor["partage"]: (False, False)}),
        "admin": (ADMIN, {decor["partage"]: (True, True), decor["seul"]: (True, True)}),
    }
    for nom, (qui, vus) in attendu.items():
        lus = {i: (a["ecrivable"], a["destructible"]) for i, a in _albums(client, qui).items()}
        assert lus == vus, nom
    # Des BOOLÉENS : `0`/`1` passerait en JSON pour un nombre.
    for a in _albums(client, ADMIN).values():
        assert isinstance(a["destructible"], bool) and isinstance(a["ecrivable"], bool)


def test_apres_etre_sorti_on_ne_se_voit_plus_rien_offrir(client, decor):
    """Qui sort l'album de la collection où il écrivait, et continue de le lire par
    l'autre, redevient un lecteur de cet album : ni destructible, ni écrivable."""
    client.delete(f"/api/albums/{decor['partage']}/collections/{decor['incubateur']}",
                  headers=MIXTE)
    lu = _albums(client, MIXTE)[decor["partage"]]
    assert (lu["ecrivable"], lu["destructible"]) == (False, False)


# ── la clause, lue seule ─────────────────────────────────────────────────────────────────
def test_clause_destruction_aux_extremites():
    assert autorisation.TOTALE.clause_destruction("a.id") == ("1", [])
    assert autorisation.Portee().clause_destruction("a.id") == ("0", [])
    # Lire n'est pas écrire : une portée qui ne fait que lire ne détruit rien.
    assert autorisation.Portee(lecture=frozenset({1})).clause_destruction("a.id") == ("0", [])


def test_clause_destruction_lie_ses_parametres_et_cumule_les_proprietaires():
    """Les ids sont LIÉS, jamais interpolés ; ils servent deux fois (dans la moitié qui
    exige, dans celle qui interdit) ; et un propriétaire écrit — l'oubli qu'AUTH-3 nomme."""
    p = autorisation.Portee(ecriture=frozenset({3}), propriete=frozenset({7}))
    sql, params = p.clause_destruction("x.album_id")
    assert params == [3, 7, 3, 7]
    assert sql.count("?") == 4 and "3" not in sql and "7" not in sql
    assert sql.count("x.album_id") == 2


def test_un_album_range_nulle_part_n_est_destructible_par_personne(db_path, client):
    """L'invariant d'AUTH-2 interdit l'orphelin, une base retouchée à la main peut le
    produire. `NOT EXISTS` seul y serait VRAI par vacuité : quiconque écrit quelque part
    aurait alors le droit de détruire un album qu'aucune règle ne lui ouvre."""
    conn = sqlite3.connect(db_path)
    try:
        aid = conn.execute("INSERT INTO albums (titre) VALUES ('Orphelin')").lastrowid
        cid = conn.execute("INSERT INTO collection (nom) VALUES ('Ailleurs')").lastrowid
        ou, params = autorisation.Portee(ecriture=frozenset({cid})).clause_destruction("a.id")
        assert conn.execute(f"SELECT 1 FROM albums a WHERE a.id = ? AND {ou}",
                            (aid, *params)).fetchone() is None
        # Et la portée totale le détruit : c'est le seul recours pour un tel album.
        ou, params = autorisation.TOTALE.clause_destruction("a.id")
        assert conn.execute(f"SELECT 1 FROM albums a WHERE a.id = ? AND {ou}",
                            (aid, *params)).fetchone() is not None
    finally:
        conn.close()


# ── le cliquet : une route qui DÉTRUIT a tranché ─────────────────────────────────────────
# L'oubli de cette garde échoue OUVERT, comme celui de l'export avant `test_droit_export` :
# une route neuve qui effacerait un album sans la poser continuerait de marcher, et aucun
# des tests du dessus ne la connaîtrait. Celui-ci lit le SOURCE des routes : toute fonction
# qui efface un album ou une planche, ou leurs fichiers, pose `_exiger_destruction` ou
# figure ici avec sa raison.
_DETRUIT = re.compile(r"DELETE\s+FROM\s+(albums|planches)\b|remove_album_files\(|remove_planche_files\(")
HORS_GARDE = {
    "sharedocs_importer": "ne retire que l'album VIDE qu'elle vient de créer dans la même "
                          "requête, quand aucun fichier n'a pu être importé : il n'a ni "
                          "planche ni seconde collection, et personne ne l'a encore vu",
}


def _fonctions_qui_detruisent():
    trouvees = {}
    for fichier in [RACINE / "main.py", *sorted((RACINE / "routes").glob("*.py"))]:
        source = fichier.read_text(encoding="utf-8")
        for noeud in ast.walk(ast.parse(source)):
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                corps = ast.get_source_segment(source, noeud)
                if _DETRUIT.search(corps):
                    trouvees[noeud.name] = "_exiger_destruction(" in corps
    return trouvees


def test_toute_route_qui_detruit_pose_la_garde_ou_dit_pourquoi_non():
    trouvees = _fonctions_qui_detruisent()
    # Le plancher d'abord : un motif qui ne trouverait plus rien approuverait tout.
    assert {"delete_album", "delete_planche", "sharedocs_importer"} <= set(trouvees), trouvees
    sans_garde = {nom for nom, gardee in trouvees.items() if not gardee}
    assert sans_garde == set(HORS_GARDE), (
        f"détruisent sans `_exiger_destruction` et sans raison écrite : "
        f"{sorted(sans_garde - set(HORS_GARDE))} ; déclarées à tort : "
        f"{sorted(set(HORS_GARDE) - sans_garde)}")
    assert all(len(raison) >= 40 for raison in HORS_GARDE.values())
