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
}


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
        a = self.auteur
        if a is None:
            par = "modifié ailleurs"
        elif a["meme_compte"]:
            par = f"modifié depuis un autre écran de ce même compte, le {a['le']} (UTC)"
        elif a["nom"] or a["login"]:
            par = f"modifié par {a['nom'] or a['login']}, le {a['le']} (UTC)"
        else:
            par = f"modifié ailleurs, le {a['le']} (UTC)"
        return (f"Conflit : {quoi} a été {par} depuis que vous l'avez vu. "
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
                    valeur: Any) -> Optional[dict]:
    """Le dernier acte du journal qui a posé `champ` à `valeur`, ou None si aucun.

    Les annulations comptent : elles sont journalisées sur l'acte qu'elles défont
    (`cible_table = 'evenement'`), et ce qu'elles posent est l'`avant` de cet acte.
    """
    lignes = conn.execute(
        "SELECT e.*, a.avant AS acte_avant, a.apres AS acte_apres FROM evenement e "
        "LEFT JOIN evenement a ON e.cible_table = 'evenement' AND a.id = e.cible_id "
        "WHERE (e.cible_table = ? AND e.cible_id = ?) "
        "   OR (e.cible_table = 'evenement' AND e.type = 'annulation' "
        "       AND a.cible_table = ? AND a.cible_id = ?) "
        "ORDER BY e.id DESC", (cible_table, cible_id, cible_table, cible_id)).fetchall()
    for e in lignes:
        if e["cible_table"] == "evenement":        # une annulation va d'« après » à « avant »
            avant, apres = _charge(e["acte_apres"]), _charge(e["acte_avant"])
        else:
            avant, apres = _charge(e["avant"]), _charge(e["apres"])
        if not egal(avant.get(champ), apres.get(champ)) and egal(apres.get(champ), valeur):
            return auteur(conn, e)
    return None


def verifier(conn: sqlite3.Connection, cible_table: str, cible_id: int, champ: str, *,
             vu: Any, actuel: Any, nouveau: Any) -> None:
    """Lève `Perime` si `champ` ne porte plus la valeur `vu` et que l'écriture l'écraserait.

    Trois cas passent. L'écran avait vu la valeur actuelle. L'écriture pose la valeur déjà
    en base : rien ne se perd. Et le dernier changement vient d'un MOTEUR (Q2) — l'OCR n'est
    qu'un pré-remplissage, l'humain l'emporte, et le texte du moteur reste au journal.
    """
    if egal(vu, actuel) or egal(nouveau, actuel):
        return
    qui = auteur_du_champ(conn, cible_table, cible_id, champ, actuel)
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
