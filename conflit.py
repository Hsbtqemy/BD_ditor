"""CONC-3, second temps — refuser un enregistrement fait sur une version périmée.

Tranché par Hugo le 2026-09-17 : la version qu'un écran a vue est la VALEUR du champ. L'écran
envoie, avec ce qu'il change, la valeur qu'il avait vue ; si la base porte autre chose, on
refuse, et on dit qui a changé le champ et quand.

Pourquoi la valeur, et pas une colonne `version`, le journal ou une date. Une colonne demande
que CHAQUE écrivain l'incrémente — un oubli reste muet — et elle vaut pour la ligne : poser un
tag périmerait la note de l'autre. Le dernier événement du journal manque les annulations,
journalisées sur `evenement` et non sur leur cible, et les régions qu'une re-passe
automatique remplace sans événement. Une date est à la seconde, quand l'Atelier enregistre
toutes les 500 ms. La valeur, elle, voit tout écrivain, au champ près. Seul un aller-retour
X→Y→X passe inaperçu — sans rien perdre, puisque le contenu est celui qu'on avait vu.

Le journal ne sert qu'à NOMMER : il ne décide jamais du refus. Un champ changé sans laisser
de trace est refusé tout de même, avec « modifié ailleurs ».
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

import journal

# Ce qu'un message peut dire d'un champ. Un champ absent se nomme par son nom de colonne.
LIBELLES = {
    "note": "la note",
    "ocr_texte": "le texte",
    "x": "la position", "y": "la position", "w": "la taille", "h": "la taille",
    "type": "le type",
    "parent_id": "le rattachement",
    # ANN-8 : des champs gardés de l'annulation d'un changement de type
    # (`undo._garder_liens_du_type`).
    "locuteur": "le locuteur",
    "presence": "le personnage montré",
    "situation": "la situation",
    # ANN-7 (tranche 1, R9) : les valeurs uniques d'un relevé, d'un doute, d'une passe.
    "variante_cle": "la variante",
    "qualificatifs": "les qualificatifs",
    "precision": "la précision",
    "lien_region_id": "le lien",
    "mots": "le passage",
    "doute": "le doute",
    "passe": "la passe",
    # Un relevé entier : un autre de la même entrée `une` posé sur la cible depuis
    # (`undo._inverser_releve`), ou un relevé qui vit sur une région dont on annule la
    # création (`undo._garder_releves_de_creation`).
    "releve": "le relevé",
}


def verrouiller(conn: sqlite3.Connection) -> None:
    """Prend le verrou d'écriture AVANT de lire la valeur actuelle d'un champ gardé.

    La garde lit, compare, puis écrit. Le module `sqlite3` n'ouvre la transaction qu'au premier
    INSERT ou UPDATE : la lecture se faisait donc HORS transaction, et deux requêtes
    simultanées lisaient toutes deux l'ancienne valeur, passaient toutes deux, et la seconde
    écrasait la première sans 409 (mesuré, `test_conflit_version`). `BEGIN IMMEDIATE` fait
    attendre la seconde — dans la limite de `busy_timeout` — jusqu'à ce que la première ait
    validé ; elle lit alors la nouvelle valeur. La transaction se valide par le `commit` de la
    route, et se défait à la fermeture de la connexion si la route refuse."""
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")


def egal(a: Any, b: Any) -> bool:
    """Deux valeurs de champ se valent-elles ? Un texte absent et un texte vide, oui : l'écran
    ne fait pas la différence, et un conflit entre les deux n'aurait rien à montrer."""
    return ("" if a is None else a) == ("" if b is None else b)


class Perime(Exception):
    """Un champ que l'appelant croyait à une valeur en porte une autre."""

    def __init__(self, cible_table: str, cible_id: int, champ: str, valeur_actuelle: Any,
                 auteur: Optional[dict]):
        self.cible_table, self.cible_id, self.champ = cible_table, cible_id, champ
        self.valeur_actuelle, self.auteur = valeur_actuelle, auteur
        super().__init__(self.message())

    def message(self) -> str:
        quoi = LIBELLES.get(self.champ, self.champ)
        e = "e" if quoi.startswith("la ") else ""      # « la note a été modifiée »
        if quoi.startswith("les "):                    # « les qualificatifs ont été modifiés »
            return self._message_pluriel(quoi)
        a = self.auteur
        if a is None:
            par = f"modifié{e} ailleurs"
        elif a["meme_compte"]:
            par = f"modifié{e} depuis un autre écran de ce même compte, le {a['le']} (UTC)"
        elif a["nom"] or a["login"]:
            par = f"modifié{e} par {a['nom'] or a['login']}, le {a['le']} (UTC)"
        else:
            par = f"modifié{e} ailleurs, le {a['le']} (UTC)"
        return (f"Conflit : {quoi} a été {par} depuis que vous l'avez vu{e}. "
                "Votre modification n'est pas enregistrée.")

    def _message_pluriel(self, quoi: str) -> str:
        a = self.auteur
        if a is None:
            par = "modifiés ailleurs"
        elif a["meme_compte"]:
            par = f"modifiés depuis un autre écran de ce même compte, le {a['le']} (UTC)"
        elif a["nom"] or a["login"]:
            par = f"modifiés par {a['nom'] or a['login']}, le {a['le']} (UTC)"
        else:
            par = f"modifiés ailleurs, le {a['le']} (UTC)"
        return (f"Conflit : {quoi} ont été {par} depuis que vous les avez vus. "
                "Votre modification n'est pas enregistrée.")

    def detail(self) -> dict:
        """Le corps du 409 : un message lisible, et de quoi reconstruire l'écran."""
        return {"message": self.message(),
                "conflit": {"cible": self.cible_table, "id": self.cible_id,
                            "champ": self.champ, "valeur_actuelle": self.valeur_actuelle,
                            "auteur": self.auteur}}


def _charge(texte: Optional[str]) -> dict:
    return json.loads(texte) if texte else {}


def auteur(conn: sqlite3.Connection, e) -> dict:
    """Qui a fait l'événement `e`, pour un message : nom affiché, login, nature, date ISO."""
    login = e["agent"]
    ligne = conn.execute("SELECT nom FROM utilisateur WHERE login = ?", (login,)).fetchone() \
        if login else None
    courant = journal.agent_courant.get()
    # Le même compte, y compris SANS compte : en mono-poste, hors proxy, aucun acte n'a de
    # login, et deux écrans de la même machine sont une seule personne.
    return {"login": login,
            "nom": ligne["nom"] if ligne else None,
            "agent_type": e["agent_type"],
            "meme_compte": e["agent_type"] == "humain" and login == courant,
            "le": (e["date"] or "").replace(" ", "T") + "Z"}


def auteur_du_champ(conn: sqlite3.Connection, cible_table: str, cible_id: int, champ: str,
                    valeur: Any, *, depuis: Optional[int] = None,
                    objet: Optional[tuple] = None) -> Optional[dict]:
    """Le dernier acte du journal qui a posé `champ` à `valeur`, ou None si aucun.

    Les annulations comptent : elles sont journalisées sur l'acte qu'elles défont
    (`cible_table = 'evenement'`), et ce qu'elles posent est l'`avant` de cet acte.

    `depuis` : l'identifiant d'un événement — seuls comptent les actes POSTÉRIEURS. C'est ce
    que demande une annulation, dont le refus dit « modifié depuis » l'acte qu'elle défait
    (ANN-8, relecture croisée de la garde des liens). Sans borne, la recherche remontait
    tout le journal du `cible_id` : elle nommait un geste d'avant l'acte comme une
    modification faite depuis, et — sous la numérotation d'avant la v30, où un identifiant
    se reprenait — l'auteur d'un ANCIEN objet, dans une collection que l'agent ne lit pas.
    Rien trouvé après l'acte : None, « modifié ailleurs ».
    """
    return auteur_des_champs(conn, ((cible_table, champ),), cible_id, valeur, depuis=depuis,
                             objet=objet)


def auteur_des_champs(conn: sqlite3.Connection, sources, cible_id: int,
                      valeur: Any, *, depuis: Optional[int] = None,
                      objet: Optional[tuple] = None) -> Optional[dict]:
    """`auteur_du_champ` pour une valeur que plusieurs sortes d'actes écrivent : `sources`,
    des couples (table, clé de la charge), lus ensemble dans l'ordre du journal — le dernier
    acte qui a posé la valeur, quelle que soit sa table.

    ANN-8 — un locuteur se pose et se retire par `bulle_locuteur` (`personnage_id`), mais un
    changement de type le retire aussi, dans un acte sur `regions` qui le range sous
    `locuteur` (et son annulation le repose) : nommer qui l'a ôté demande de lire les deux.

    `objet` (ANN-7) : `(clé, valeur)` — seuls comptent les actes dont la charge (avant ou
    après) porte cette clé à cette valeur. Les actes sur un RELEVÉ ciblent sa RÉGION (R10),
    que plusieurs relevés partagent : sans ce filtre, la variante d'un autre relevé de la
    même bulle nommerait son auteur à la place.
    """
    tables = [t for t, _ in sources]
    cle = dict(sources)
    marques = ", ".join("?" * len(tables))
    lignes = conn.execute(
        "SELECT e.*, a.avant AS acte_avant, a.apres AS acte_apres, "
        "       COALESCE(a.cible_table, e.cible_table) AS source FROM evenement e "
        "LEFT JOIN evenement a ON e.cible_table = 'evenement' AND a.id = e.cible_id "
        f"WHERE (e.cible_table IN ({marques}) AND e.cible_id = ?) "
        "   OR (e.cible_table = 'evenement' AND e.type = 'annulation' "
        f"       AND a.cible_table IN ({marques}) AND a.cible_id = ?) "
        "ORDER BY e.id DESC", (*tables, cible_id, *tables, cible_id)).fetchall()
    if depuis is not None:                         # cf. `auteur_du_champ`
        lignes = [e for e in lignes if e["id"] > depuis]
    for e in lignes:
        champ = cle[e["source"]]
        if e["cible_table"] == "evenement":        # une annulation va d'« après » à « avant »
            avant, apres = _charge(e["acte_apres"]), _charge(e["acte_avant"])
        else:
            avant, apres = _charge(e["avant"]), _charge(e["apres"])
        if objet is not None and objet[1] not in (avant.get(objet[0]), apres.get(objet[0])):
            continue
        if not egal(avant.get(champ), apres.get(champ)) and egal(apres.get(champ), valeur):
            return auteur(conn, e)
    return None


def verifier(conn: sqlite3.Connection, cible_table: str, cible_id: int, champ: str, *,
             vu: Any, actuel: Any, nouveau: Any, depuis: Optional[int] = None,
             sources=None, objet: Optional[tuple] = None) -> None:
    """Lève `Perime` si `champ` ne porte plus la valeur `vu` et que l'écriture l'écraserait.

    Trois cas passent. L'écran avait vu la valeur actuelle. L'écriture pose la valeur déjà
    en base : rien ne se perd. Et le dernier changement vient d'un MOTEUR (Q2) — l'OCR n'est
    qu'un pré-remplissage, l'humain l'emporte, et le texte du moteur reste au journal.
    `depuis` : cf. `auteur_du_champ` — une annulation le passe, une route non.

    `sources` : pour un champ que plusieurs sortes d'actes écrivent, les couples (table, clé
    de la charge) où chercher l'auteur (`auteur_des_champs`) ; sinon `champ` sous
    `cible_table`. CONC-4 — un locuteur s'écrit sous `bulle_locuteur` (`personnage_id`), et
    un changement de type le retire sous `regions` (`locuteur`) : le 409 d'une attribution
    périmée nomme l'un ou l'autre.
    """
    if egal(vu, actuel) or egal(nouveau, actuel):
        return
    qui = (auteur_des_champs(conn, sources, cible_id, actuel, depuis=depuis, objet=objet)
           if sources else auteur_du_champ(conn, cible_table, cible_id, champ, actuel,
                                           depuis=depuis, objet=objet))
    if qui is not None and qui["agent_type"] == "moteur":
        return
    raise Perime(cible_table, cible_id, champ, actuel, qui)


def _contient(snap: dict, region_id: int) -> bool:
    if snap.get("id") == region_id:
        return True
    return any(_contient(enfant, region_id) for enfant in snap.get("enfants", []))


def suppression_de_region(conn: sqlite3.Connection, region_id: int) -> Optional[dict]:
    """La suppression qui a emporté cette région — directe, ou par celle d'un parent —, avec
    sa planche et son auteur. None si le journal n'en garde aucune.

    Le filtre `LIKE` ne sert qu'à écarter vite : la décision se prend sur l'instantané profond
    relu, pour qu'un `"id": 12` ne réponde pas pour la région 123.
    """
    lignes = conn.execute(
        "SELECT * FROM evenement WHERE cible_table = 'regions' AND type = 'suppression' "
        "AND (cible_id = ? OR avant LIKE ?) ORDER BY id DESC",
        (region_id, f'%"id": {region_id}%')).fetchall()
    for e in lignes:
        snap = _charge(e["avant"])
        if e["cible_id"] == region_id or _contient(snap, region_id):
            return {"planche_id": snap.get("planche_id"), "auteur": auteur(conn, e)}
    return None
