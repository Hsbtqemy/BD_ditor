"""CONC-3, second temps — refuser un enregistrement fait sur une version périmée.

Tranché par Hugo le 2026-09-17 : la version qu'un écran a vue est la VALEUR du champ, pas une
colonne, pas le journal, pas une date. L'écran envoie, avec ce qu'il change, la valeur qu'il
avait vue ; si la base porte autre chose, le serveur refuse par un 409 qui nomme qui a changé
le champ et quand. Ces tests tiennent le serveur : routes d'annotation et de région,
annulation, case supprimée. L'écran a sa propre garde.
"""
import sqlite3
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import autorisation  # noqa: E402
import conflit  # noqa: E402
import database  # noqa: E402
import journal  # noqa: E402
import main  # noqa: E402

A = {"Remote-User": "personne-a", "Remote-Groups": "bd-admins"}
B = {"Remote-User": "personne-b", "Remote-Groups": "bd-admins"}
NOMMEE_A = {**A, "Remote-Name": "Alice Dupont"}
NOMME_B = {**B, "Remote-Name": "Bob Martin"}


def _bulle(client, planche_id, **champs):
    corps = {"type": "bulle", "x": 0, "y": 0, "w": 10, "h": 10, **champs}
    rep = client.post(f"/api/planches/{planche_id}/regions", json=corps)
    assert rep.status_code in (200, 201), rep.text
    rid = rep.json()["id"]
    if "ocr_texte" in champs:          # la création ne pose pas le texte : on le pose ensuite
        assert client.put(f"/api/regions/{rid}",
                          json={"ocr_texte": champs["ocr_texte"]}).status_code == 200
    return rid


def _region(client, planche_id, rid, headers=A):
    for r in client.get(f"/api/planches/{planche_id}/regions", headers=headers).json():
        if r["id"] == rid:
            return r
    return None


def _annotation(client, rid, headers=None):
    a = client.get(f"/api/regions/{rid}/annotation", headers=headers).json()
    return a["note"], {t["label"] for t in a["tags"]}


def _derriere_le_proxy(monkeypatch, client=None):
    """Place la suite du test derrière le proxy. Avec `client`, les deux personnes ouvrent
    une page : c'est `/api/moi`, appelé à chaque chargement, qui inscrit leur nom affiché
    dans `utilisateur` — un écran réel le fait avant tout enregistrement."""
    monkeypatch.setattr(main, "AUTH_PROXY", True)
    monkeypatch.setattr(autorisation, "AUTH_PROXY", True)
    if client is not None:
        for qui in (NOMMEE_A, NOMME_B):
            assert client.get("/api/moi", headers=qui).status_code == 200


# --------------------------------------------------------------------------- #
# Q1 — la valeur vue, champ par champ
# --------------------------------------------------------------------------- #
def test_deux_notes_la_seconde_est_refusee_et_nomme_la_premiere(client, planche, monkeypatch):
    """La mesure 2 : A et B ont vu la note vide ; A enregistre, puis B. B n'écrase plus A."""
    rid = _bulle(client, planche["id"])
    _derriere_le_proxy(monkeypatch, client)
    rep = client.put(f"/api/regions/{rid}/annotation",
                     json={"note": "note de A", "note_vue": ""}, headers=NOMMEE_A)
    assert rep.status_code == 200, rep.text

    rep = client.put(f"/api/regions/{rid}/annotation",
                     json={"note": "note de B", "note_vue": ""}, headers=NOMME_B)
    assert rep.status_code == 409, rep.text
    d = rep.json()["detail"]
    assert d["conflit"]["champ"] == "note"
    assert d["conflit"]["valeur_actuelle"] == "note de A"
    auteur = d["conflit"]["auteur"]
    assert (auteur["nom"], auteur["login"], auteur["meme_compte"]) == (
        "Alice Dupont", "personne-a", False)
    assert auteur["le"].endswith("Z") and "T" in auteur["le"]
    assert "Alice Dupont" in d["message"]
    assert _annotation(client, rid, A)[0] == "note de A", "la note de A a été écrasée"


def test_la_mesure_3_le_texte_transcrit_n_est_plus_ecrase(client, planche, monkeypatch):
    rid = _bulle(client, planche["id"], ocr_texte="TEXTE INITIAL")
    _derriere_le_proxy(monkeypatch, client)
    assert client.put(f"/api/regions/{rid}", headers=B,
                      json={"ocr_texte": "TEXTE DE B",
                            "vu": {"ocr_texte": "TEXTE INITIAL"}}).status_code == 200
    rep = client.put(f"/api/regions/{rid}", headers=A,
                     json={"ocr_texte": "TEXTE INITIAL + A",
                           "vu": {"ocr_texte": "TEXTE INITIAL"}})
    assert rep.status_code == 409, rep.text
    assert rep.json()["detail"]["conflit"]["auteur"]["login"] == "personne-b"
    assert _region(client, planche["id"], rid)["ocr_texte"] == "TEXTE DE B"


def test_la_garde_est_au_champ_pas_a_la_ligne(client, planche, monkeypatch):
    """B déplace la bulle ; A, qui avait vu le texte à jour, le corrige : aucun conflit."""
    rid = _bulle(client, planche["id"], ocr_texte="TEXTE")
    _derriere_le_proxy(monkeypatch, client)
    assert client.put(f"/api/regions/{rid}", json={"x": 40, "vu": {"x": 0}},
                      headers=B).status_code == 200
    rep = client.put(f"/api/regions/{rid}", headers=A,
                     json={"ocr_texte": "TEXTE CORRIGÉ", "vu": {"ocr_texte": "TEXTE"}})
    assert rep.status_code == 200, rep.text


def test_la_geometrie_perimee_est_refusee(client, planche, monkeypatch):
    rid = _bulle(client, planche["id"])
    _derriere_le_proxy(monkeypatch, client)
    assert client.put(f"/api/regions/{rid}", json={"x": 40, "vu": {"x": 0}},
                      headers=B).status_code == 200
    rep = client.put(f"/api/regions/{rid}", json={"x": 60, "vu": {"x": 0}}, headers=A)
    assert rep.status_code == 409, rep.text
    assert rep.json()["detail"]["conflit"]["champ"] == "x"


def test_les_tags_n_ont_pas_de_garde(client, planche, monkeypatch):
    """Q3 — ajouter ou retirer un tag ne rend jamais 409, même quand la note a changé."""
    rid = _bulle(client, planche["id"])
    _derriere_le_proxy(monkeypatch, client)
    client.put(f"/api/regions/{rid}/annotation", json={"note": "note de A"}, headers=A)
    rep = client.put(f"/api/regions/{rid}/annotation", json={"tags_ajoutes": ["tag-de-b"]},
                     headers=B)
    assert rep.status_code == 200, rep.text
    rep = client.put(f"/api/regions/{rid}/annotation", json={"tags_retires": ["absent"]},
                     headers=B)
    assert rep.status_code == 200, rep.text
    assert _annotation(client, rid, A) == ("note de A", {"tag-de-b"})


def test_ecrire_la_valeur_deja_en_base_n_est_pas_un_conflit(client, planche, monkeypatch):
    """Rien ne se perd : le conflit n'aurait rien à montrer."""
    rid = _bulle(client, planche["id"])
    _derriere_le_proxy(monkeypatch, client)
    client.put(f"/api/regions/{rid}/annotation", json={"note": "même", "note_vue": ""},
               headers=A)
    rep = client.put(f"/api/regions/{rid}/annotation", json={"note": "même", "note_vue": ""},
                     headers=B)
    assert rep.status_code == 200, rep.text


def test_sans_valeur_vue_le_dernier_gagne_comme_avant(client, planche, monkeypatch):
    """Q8 — la valeur vue est facultative pour l'API : outils et appelants existants."""
    rid = _bulle(client, planche["id"], ocr_texte="DÉPART")
    _derriere_le_proxy(monkeypatch, client)
    client.put(f"/api/regions/{rid}", json={"ocr_texte": "DE B"}, headers=B)
    assert client.put(f"/api/regions/{rid}", json={"ocr_texte": "DE A"},
                      headers=A).status_code == 200
    client.put(f"/api/regions/{rid}/annotation", json={"note": "de B"}, headers=B)
    assert client.put(f"/api/regions/{rid}/annotation", json={"note": "de A"},
                      headers=A).status_code == 200
    assert _region(client, planche["id"], rid)["ocr_texte"] == "DE A"
    assert _annotation(client, rid, A)[0] == "de A"


def test_un_champ_vu_hors_liste_est_refuse(client, planche):
    rid = _bulle(client, planche["id"])
    rep = client.put(f"/api/regions/{rid}", json={"x": 3, "vu": {"ordre": 1}})
    assert rep.status_code == 422, rep.text


# --------------------------------------------------------------------------- #
# Q2 — un moteur ne gagne pas contre un humain
# --------------------------------------------------------------------------- #
def _ecrire_comme_un_moteur(rid, texte):
    conn = database.get_connection()
    try:
        avant = journal.snapshot_region(conn, rid)
        conn.execute("UPDATE regions SET ocr_texte = ? WHERE id = ?", (texte, rid))
        journal.journaliser(conn, "modification", "regions", rid, avant=avant,
                            apres=journal.snapshot_region(conn, rid), agent="easyocr",
                            agent_type="moteur")
        conn.commit()
    finally:
        conn.close()


def test_un_texte_pose_par_un_moteur_ne_bloque_pas_l_humain(client, planche, monkeypatch):
    """L'OCR remplit une bulle que l'écran avait vue vide : la saisie humaine passe, et le
    texte du moteur reste au journal."""
    rid = _bulle(client, planche["id"])
    _ecrire_comme_un_moteur(rid, "TEXTE OCR")
    _derriere_le_proxy(monkeypatch, client)
    rep = client.put(f"/api/regions/{rid}", headers=A,
                     json={"ocr_texte": "TEXTE HUMAIN", "vu": {"ocr_texte": ""}})
    assert rep.status_code == 200, rep.text
    assert _region(client, planche["id"], rid)["ocr_texte"] == "TEXTE HUMAIN"


def test_un_changement_sans_trace_est_refuse_quand_meme(client, planche):
    """Le journal NOMME, il ne décide pas : un champ changé sans événement est un conflit."""
    rid = _bulle(client, planche["id"], ocr_texte="VU")
    conn = database.get_connection()
    try:
        conn.execute("UPDATE regions SET ocr_texte = 'CHANGÉ EN DOUCE' WHERE id = ?", (rid,))
        conn.commit()
    finally:
        conn.close()
    rep = client.put(f"/api/regions/{rid}", json={"ocr_texte": "MOI", "vu": {"ocr_texte": "VU"}})
    assert rep.status_code == 409, rep.text
    assert rep.json()["detail"]["conflit"]["auteur"] is None
    assert "modifié ailleurs" in rep.json()["detail"]["message"]


def _simultanes(envois):
    """Lance les envois dans deux fils, le second 50 ms après le premier, et rend leur issue :
    "ok", "conflit" pour un 409 de version périmée, ou le code et le détail sinon. Un 409
    « database is locked » n'est PAS un conflit : le compter pour tel rendrait ce test vert
    pour une mauvaise raison."""
    issues = {}

    def envoyer(n, f):
        r = f()
        detail = r.json().get("detail") if r.status_code >= 400 else None
        if r.status_code == 200:
            issues[n] = "ok"
        elif r.status_code == 409 and isinstance(detail, dict) and "conflit" in detail:
            issues[n] = "conflit"
        else:
            issues[n] = f"{r.status_code} {detail}"
    fils = [threading.Thread(target=envoyer, args=(n, f)) for n, f in enumerate(envois)]
    for fil in fils:
        fil.start()
        time.sleep(0.05)
    for fil in fils:
        fil.join()
    return [issues[n] for n in range(len(envois))]


def _rendez_vous_apres_lecture(monkeypatch):
    """Fait attendre chaque requête, APRÈS qu'elle a lu la valeur actuelle, que l'autre ait lu
    à son tour — deux secondes au plus. Sans verrou, les deux lisent l'ancienne valeur, et la
    course se produit à coup sûr ; avec, la seconde ne lit qu'une fois la première validée, et
    l'attente de la première expire. `conflit.verifier` est le point commun : il reçoit la
    valeur actuelle déjà lue, dans les deux routes comme dans l'annulation."""
    verifier = conflit.verifier
    rendez_vous = threading.Barrier(2, timeout=2)

    def apres_lecture(*args, **kwargs):
        try:
            rendez_vous.wait()
        except threading.BrokenBarrierError:
            pass
        return verifier(*args, **kwargs)
    monkeypatch.setattr(conflit, "verifier", apres_lecture)


def test_deux_notes_simultanees_ne_passent_pas_toutes_deux_la_garde(client, planche, monkeypatch):
    """La garde LIT la valeur actuelle, puis écrit. Lue hors transaction d'écriture — le module
    `sqlite3` n'en ouvre une qu'au premier INSERT ou UPDATE —, deux requêtes simultanées
    lisaient toutes deux l'ancienne valeur et passaient toutes deux : la seconde écrasait la
    première sans 409. Trouvé par un mutant de l'écran qui survivait, à deux navigateurs."""
    rid = _bulle(client, planche["id"])
    _rendez_vous_apres_lecture(monkeypatch)
    issues = _simultanes([
        lambda: client.put(f"/api/regions/{rid}/annotation", json={"note": "A", "note_vue": ""}),
        lambda: client.put(f"/api/regions/{rid}/annotation", json={"note": "B", "note_vue": ""})])
    assert sorted(issues) == ["conflit", "ok"], issues
    gagnante = "A" if issues[0] == "ok" else "B"
    assert client.get(f"/api/regions/{rid}/annotation").json()["note"] == gagnante


def test_deux_textes_simultanes_ne_passent_pas_tous_deux_la_garde(client, planche, monkeypatch):
    """Même course sur une région : la valeur actuelle vient de la lecture de la région."""
    rid = _bulle(client, planche["id"], ocr_texte="VU")
    _rendez_vous_apres_lecture(monkeypatch)
    issues = _simultanes([
        lambda: client.put(f"/api/regions/{rid}", json={"ocr_texte": "A", "vu": {"ocr_texte": "VU"}}),
        lambda: client.put(f"/api/regions/{rid}", json={"ocr_texte": "B", "vu": {"ocr_texte": "VU"}})])
    assert sorted(issues) == ["conflit", "ok"], issues
    gagnant = "A" if issues[0] == "ok" else "B"
    assert _region(client, planche["id"], rid)["ocr_texte"] == gagnant


def test_une_annulation_et_un_enregistrement_simultanes_ne_passent_pas_tous_deux(
        client, planche, monkeypatch):
    """Même course entre Ctrl+Z et l'enregistrement d'un autre : l'annulation garde aussi ce
    qu'elle lit (Q4), et doit le lire sous le même verrou."""
    rid = _bulle(client, planche["id"])
    _derriere_le_proxy(monkeypatch, client)
    # L'identité NOMMÉE partout, comme un écran réel : un nom différent de celui que
    # `/api/moi` a inscrit fait réécrire le miroir `utilisateur` sur la connexion de la
    # requête, AVANT la route — cette écriture prenait le verrou et masquait la course.
    client.put(f"/api/regions/{rid}", json={"x": 50}, headers=NOMMEE_A)
    _rendez_vous_apres_lecture(monkeypatch)
    issues = _simultanes([
        lambda: client.post("/api/undo", headers=NOMMEE_A),
        lambda: client.put(f"/api/regions/{rid}", json={"x": 80, "vu": {"x": 50}},
                           headers=NOMME_B)])
    assert sorted(issues) == ["conflit", "ok"], issues
    assert _region(client, planche["id"], rid)["x"] == (0 if issues[0] == "ok" else 80)


def test_le_message_accorde_le_participe_au_champ(client, planche):
    """« la note a été modifiée », « le texte a été modifié » : le message sort de l'instance
    (outils, appelants de l'API) tel quel, et une faute d'accord s'y lit."""
    rid = _bulle(client, planche["id"], ocr_texte="VU")
    client.put(f"/api/regions/{rid}/annotation", json={"note": "écran 1", "note_vue": ""})
    note = client.put(f"/api/regions/{rid}/annotation",
                      json={"note": "écran 2", "note_vue": ""}).json()["detail"]["message"]
    assert "la note a été modifiée " in note and "l'avez vue." in note, note
    client.put(f"/api/regions/{rid}", json={"ocr_texte": "AUTRE", "vu": {"ocr_texte": "VU"}})
    texte = client.put(f"/api/regions/{rid}", json={"ocr_texte": "MOI", "vu": {"ocr_texte": "VU"}}
                       ).json()["detail"]["message"]
    assert "le texte a été modifié " in texte and "l'avez vu." in texte, texte


# --------------------------------------------------------------------------- #
# Q7 — qui : le nom affiché, ou « un autre écran de ce même compte »
# --------------------------------------------------------------------------- #
def test_le_meme_compte_ne_se_nomme_pas_lui_meme(client, planche, monkeypatch):
    """Compte collectif, ou une personne avec deux onglets : le même login."""
    rid = _bulle(client, planche["id"])
    _derriere_le_proxy(monkeypatch, client)
    client.put(f"/api/regions/{rid}/annotation", json={"note": "écran 1", "note_vue": ""},
               headers=NOMMEE_A)
    rep = client.put(f"/api/regions/{rid}/annotation", json={"note": "écran 2", "note_vue": ""},
                     headers=NOMMEE_A)
    assert rep.status_code == 409, rep.text
    d = rep.json()["detail"]
    assert d["conflit"]["auteur"]["meme_compte"] is True
    assert "autre écran de ce même compte" in d["message"]
    assert "Alice Dupont" not in d["message"]


def test_en_mono_poste_deux_ecrans_sont_le_meme_compte(client, planche):
    """Hors proxy, aucun acte n'a de login : le message ne nomme personne, et ne dit pas
    « None »."""
    rid = _bulle(client, planche["id"])
    client.put(f"/api/regions/{rid}/annotation", json={"note": "écran 1", "note_vue": ""})
    rep = client.put(f"/api/regions/{rid}/annotation", json={"note": "écran 2", "note_vue": ""})
    assert rep.status_code == 409, rep.text
    d = rep.json()["detail"]
    assert d["conflit"]["auteur"]["meme_compte"] is True
    assert "None" not in d["message"]


def test_un_acte_d_avant_le_proxy_ne_se_nomme_pas_none(client, planche, monkeypatch):
    """Une note écrite en mono-poste (aucun login au journal), puis l'instance passée derrière
    le proxy : le conflit ne vient pas du même compte, et n'a aucun nom à dire."""
    rid = _bulle(client, planche["id"])
    client.put(f"/api/regions/{rid}/annotation", json={"note": "d'avant le proxy"})
    _derriere_le_proxy(monkeypatch, client)
    rep = client.put(f"/api/regions/{rid}/annotation", json={"note": "de B", "note_vue": ""},
                     headers=B)
    assert rep.status_code == 409, rep.text
    d = rep.json()["detail"]
    assert d["conflit"]["auteur"]["meme_compte"] is False
    assert "None" not in d["message"] and "modifiée ailleurs" in d["message"]


def test_une_annulation_est_nommee_comme_auteur(client, planche, monkeypatch):
    """B a vu la note de A ; A l'annule ; B enregistre sur ce qu'il avait vu : refusé, et
    c'est A, l'autrice de l'annulation, qui est nommée."""
    rid = _bulle(client, planche["id"])
    _derriere_le_proxy(monkeypatch, client)
    client.put(f"/api/regions/{rid}/annotation", json={"note": "départ"}, headers=B)
    client.put(f"/api/regions/{rid}/annotation",
               json={"note": "note de A", "note_vue": "départ"}, headers=NOMMEE_A)
    assert client.post("/api/undo", headers=NOMMEE_A).status_code == 200
    rep = client.put(f"/api/regions/{rid}/annotation",
                     json={"note": "note de B", "note_vue": "note de A"}, headers=B)
    assert rep.status_code == 409, rep.text
    assert rep.json()["detail"]["conflit"]["auteur"]["login"] == "personne-a"


# --------------------------------------------------------------------------- #
# Q4 — l'annulation ne rend que ce que l'acte a changé, et se garde aussi
# --------------------------------------------------------------------------- #
def test_annuler_un_deplacement_ne_defait_pas_la_transcription_de_l_autre(
        client, planche, monkeypatch):
    """Défaut LU le 2026-09-17, et vu ROUGE sur le code d'avant : `_restaurer_region_cols`
    réécrivait TOUTES les colonnes depuis l'instantané `avant`. A déplace la bulle, B la
    transcrit, A fait Ctrl+Z : le déplacement devait être défait, et le texte de B effacé
    avec lui."""
    rid = _bulle(client, planche["id"])
    _derriere_le_proxy(monkeypatch, client)

    assert client.put(f"/api/regions/{rid}", json={"x": 50}, headers=A).status_code == 200
    assert client.put(f"/api/regions/{rid}", json={"ocr_texte": "TEXTE DE B"},
                      headers=B).status_code == 200

    rep = client.post("/api/undo", headers=A)
    assert rep.status_code == 200, rep.text
    r = _region(client, planche["id"], rid, A)
    assert r["x"] == 0, "le déplacement de A n'a pas été défait"
    assert r["ocr_texte"] == "TEXTE DE B", "annuler le déplacement de A a effacé le texte de B"


def test_annuler_un_deplacement_modifie_depuis_est_refuse(client, planche, monkeypatch):
    rid = _bulle(client, planche["id"])
    _derriere_le_proxy(monkeypatch, client)
    client.put(f"/api/regions/{rid}", json={"x": 50}, headers=A)
    client.put(f"/api/regions/{rid}", json={"x": 80}, headers=NOMME_B)
    rep = client.post("/api/undo", headers=A)
    assert rep.status_code == 409, rep.text
    assert rep.json()["detail"]["conflit"]["auteur"]["nom"] == "Bob Martin"
    assert _region(client, planche["id"], rid)["x"] == 80, "Ctrl+Z a écrasé le geste de B"


def test_annuler_sa_note_modifiee_depuis_est_refuse(client, planche, monkeypatch):
    rid = _bulle(client, planche["id"])
    _derriere_le_proxy(monkeypatch, client)
    client.put(f"/api/regions/{rid}/annotation", json={"note": "de A"}, headers=A)
    client.put(f"/api/regions/{rid}/annotation", json={"note": "de B"}, headers=B)
    rep = client.post("/api/undo", headers=A)
    assert rep.status_code == 409, rep.text
    assert _annotation(client, rid, A)[0] == "de B"


def test_annuler_seul_rend_toujours_l_etat_d_avant(client, planche, monkeypatch):
    """Le contrepoint : sans personne d'autre, les gardes ne refusent rien."""
    rid = _bulle(client, planche["id"], ocr_texte="AVANT")
    _derriere_le_proxy(monkeypatch, client)
    client.put(f"/api/regions/{rid}", json={"x": 7, "ocr_texte": "APRÈS"}, headers=A)
    assert client.post("/api/undo", headers=A).status_code == 200
    r = _region(client, planche["id"], rid)
    assert (r["x"], r["ocr_texte"]) == (0, "AVANT")


def test_annuler_la_creation_d_une_region_travaillee_par_un_autre_est_refuse(
        client, planche, monkeypatch):
    """Supprimer la région emporterait le texte de B, sans instantané pour le rendre."""
    _derriere_le_proxy(monkeypatch, client)
    rep = client.post(f"/api/planches/{planche['id']}/regions", headers=A,
                      json={"type": "bulle", "x": 0, "y": 0, "w": 10, "h": 10})
    rid = rep.json()["id"]
    client.put(f"/api/regions/{rid}", json={"ocr_texte": "TEXTE DE B"}, headers=B)
    rep = client.post("/api/undo", headers=A)
    assert rep.status_code == 409, rep.text
    assert _region(client, planche["id"], rid) is not None


# --------------------------------------------------------------------------- #
# Q5 — une case supprimée : 410 nommé si l'on lit la planche, 404 sinon
# --------------------------------------------------------------------------- #
def test_ecrire_sur_une_case_supprimee_rend_un_410_nomme(client, planche, monkeypatch):
    rid = _bulle(client, planche["id"])
    _derriere_le_proxy(monkeypatch, client)
    assert client.delete(f"/api/regions/{rid}", headers=NOMMEE_A).status_code == 204
    for rep in (client.put(f"/api/regions/{rid}", json={"x": 55}, headers=B),
                client.put(f"/api/regions/{rid}/annotation", json={"note": "x"}, headers=B),
                client.delete(f"/api/regions/{rid}", headers=B)):
        assert rep.status_code == 410, rep.text
        d = rep.json()["detail"]
        assert d["suppression"]["auteur"]["nom"] == "Alice Dupont"
        assert "supprimée par Alice Dupont" in d["message"]


def test_une_bulle_emportee_avec_sa_case_rend_aussi_un_410(client, planche, monkeypatch):
    case = client.post(f"/api/planches/{planche['id']}/regions",
                       json={"type": "case", "x": 0, "y": 0, "w": 100, "h": 100}).json()["id"]
    bulle = client.post(f"/api/planches/{planche['id']}/regions",
                        json={"type": "bulle", "x": 5, "y": 5, "w": 10, "h": 10,
                              "parent_id": case}).json()["id"]
    _derriere_le_proxy(monkeypatch, client)
    assert client.delete(f"/api/regions/{case}", headers=A).status_code == 204
    rep = client.put(f"/api/regions/{bulle}", json={"ocr_texte": "x"}, headers=B)
    assert rep.status_code == 410, rep.text


def test_qui_ne_lit_pas_la_planche_garde_le_404(client, planche, monkeypatch, db_path):
    """Ni l'existence passée ni son auteur ne fuient vers qui ne voit pas l'album."""
    rid = _bulle(client, planche["id"])
    _derriere_le_proxy(monkeypatch, client)
    assert client.delete(f"/api/regions/{rid}", headers=NOMMEE_A).status_code == 204
    c = sqlite3.connect(db_path)
    try:
        assert c.execute("SELECT COUNT(*) FROM collection_acces WHERE principal = 'inconnu'"
                         ).fetchone()[0] == 0
    finally:
        c.close()
    rep = client.put(f"/api/regions/{rid}", json={"x": 1}, headers={"Remote-User": "inconnu"})
    assert rep.status_code == 404, rep.text
    assert "Alice" not in rep.text and "personne-a" not in rep.text
