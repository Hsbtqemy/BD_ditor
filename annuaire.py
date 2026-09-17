"""AUTH-6 — lire l'annuaire, pour COMPOSER. Jamais pour authentifier, jamais pour autoriser.

Décidé le 2026-09-09, construit à partir du 2026-09-17 (étape 1 de l'ordre d'AUTH-12). Le but
n'est pas le diagnostic mais la composition : connaître les comptes et les groupes qui
EXISTENT, pour attribuer des accès sans deviner un nom dans un champ libre, et pour signaler
un accès donné à un groupe qui n'existe plus.

TROIS actes distincts, et ce module n'en fait qu'un. AUTHENTIFIER, c'est Authelia : il dit
QUI frappe, et l'application le croit sur `Remote-User` (AUTH-1). AUTORISER, c'est
`autorisation.py` : il tranche sur les groupes que le portail transmet dans `Remote-Groups`,
requête par requête, et il n'importe RIEN d'ici — un test le verrouille. LIRE l'annuaire,
c'est ce module : une photographie des comptes et des groupes, prise à l'ouverture d'une vue
d'administration, qui ne change aucune portée. Sans cette distinction écrite, le prochain
lecteur conclurait que l'invariant d'AUTH-1 a sauté ; il tient entier.

Tranché le 2026-09-17 :
- le protocole est l'API GraphQL de LLDAP, derrière l'interface étroite de ce module
  (`lire` → `Lecture`) : changer d'annuaire, ce serait réécrire `_lire_lldap` et rien d'autre ;
- le compte de service est dans `lldap_strict_readonly` SEUL — ce module n'écrit rien ;
- aucun cache, aucune copie en base ni au journal : une lecture à chaque ouverture, bornée
  par `DELAI_S`, et `duree_ms` pour mesurer avant d'envisager mieux ;
- une panne rend `non_verifie` et ne bloque rien : elle ne déclare jamais un accès mort.

Ce module n'importe ni `main`, ni `socle`, ni `autorisation` : il est une feuille.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

import config

# Le délai TOTAL d'une lecture, connexion comprise. Au-delà, la vue s'affiche avec ce que
# l'application sait seule, et le dit (tranché par la coordination le 2026-09-17).
DELAI_S = 3.0

# Les groupes intégrés de LLDAP, lus dans `/app/bootstrap.sh` de l'image 0.6.3 : ils disent ce
# qu'un compte peut faire DANS L'ANNUAIRE, jamais dans l'application.
GROUPES_DE_ROLE = frozenset({"lldap_admin", "lldap_password_manager", "lldap_strict_readonly"})

# La doublure : des données fixes, à la forme de la réponse GraphQL, que les tests et l'écran
# chargent sans annuaire. Elle passe par le MÊME analyseur que la lecture réelle.
DOUBLURE = Path(__file__).resolve().parent / "tests" / "doublures" / "annuaire.json"
PREFIXE_DOUBLURE = "doublure:"

# Une seule requête rend tout : les comptes avec leurs groupes, et les groupes (dont ceux qui
# n'ont aucun membre). Les membres d'un groupe se déduisent des comptes.
REQUETE = ("query LireAnnuaire { users(filters: null) { id email displayName "
           "groups { id displayName } } groups { id displayName } }")


@dataclass(frozen=True)
class CompteAnnuaire:
    login: str
    nom: Optional[str]
    courriel: Optional[str]
    groupes: tuple[str, ...]


@dataclass(frozen=True)
class GroupeAnnuaire:
    id: Optional[int]
    nom: str
    membres: tuple[str, ...]


@dataclass(frozen=True)
class Lecture:
    """Ce que la lecture a obtenu. `etat` : "lu" | "non_verifie" | "sans_annuaire".

    Hors de "lu", `comptes` et `groupes` sont VIDES et ne veulent rien dire : l'appelant lit
    `etat` avant tout, et un compte absent d'une lecture ratée n'est pas un compte absent."""
    etat: str
    source: Optional[str] = None
    comptes: tuple[CompteAnnuaire, ...] = ()
    groupes: tuple[GroupeAnnuaire, ...] = ()
    lu_le: Optional[str] = None
    duree_ms: Optional[int] = None
    motif: Optional[str] = None          # "delai" | "refus" | "reponse_illisible"
    lien: Optional[str] = None

    @property
    def lu(self) -> bool:
        return self.etat == "lu"


class _Illisible(Exception):
    """La réponse n'a pas la forme attendue."""


def lire(*, transport: Optional[httpx.BaseTransport] = None) -> Lecture:
    """Lit l'annuaire MAINTENANT, en `DELAI_S` au plus, et ne lève jamais.

    La configuration se lit à l'APPEL, pas à l'import : les tests la remplacent, et un module
    qui l'aurait figée les ferait mesurer autre chose que ce qu'ils posent. `transport` sert
    aux tests seuls (une doublure de réseau)."""
    adresse = config.ANNUAIRE_ADRESSE
    lien = config.ANNUAIRE_URL or None
    if not adresse:
        return Lecture("sans_annuaire", lien=lien)
    if adresse.startswith(PREFIXE_DOUBLURE):
        return _lire_doublure(adresse[len(PREFIXE_DOUBLURE):], lien)
    if not (config.ANNUAIRE_COMPTE and config.ANNUAIRE_MOT_DE_PASSE):
        # Une adresse sans identifiant de service est une erreur de CONFIGURATION : l'annuaire
        # n'a pas refusé, on ne lui a rien demandé — mais la vue doit dire qu'elle n'a pas pu
        # vérifier, et non qu'il n'y a pas d'annuaire.
        return Lecture("non_verifie", source="lldap", motif="refus", lien=lien)
    debut = time.monotonic()
    try:
        comptes, groupes = _lire_lldap(adresse, debut, transport)
    except httpx.TimeoutException:
        return Lecture("non_verifie", source="lldap", motif="delai", lien=lien)
    except _Refus:
        return Lecture("non_verifie", source="lldap", motif="refus", lien=lien)
    except httpx.HTTPError:
        # Connexion refusée, nom introuvable, coupure : l'annuaire ne répond pas. Le motif
        # est le même que le délai dépassé, parce que la conduite à tenir est la même.
        return Lecture("non_verifie", source="lldap", motif="delai", lien=lien)
    except (_Illisible, ValueError, KeyError, TypeError):
        return Lecture("non_verifie", source="lldap", motif="reponse_illisible", lien=lien)
    return Lecture("lu", source="lldap", comptes=comptes, groupes=groupes,
                   lu_le=_maintenant_iso(), duree_ms=int((time.monotonic() - debut) * 1000),
                   lien=lien)


class _Refus(Exception):
    """L'annuaire a répondu, et a refusé : identifiant faux, ou droits insuffisants."""


def _reste(debut: float) -> float:
    reste = DELAI_S - (time.monotonic() - debut)
    if reste <= 0:
        raise httpx.ReadTimeout("délai de lecture de l'annuaire dépassé")
    return reste


def _lire_lldap(adresse: str, debut: float,
                transport: Optional[httpx.BaseTransport]) -> tuple[tuple, tuple]:
    """Connexion simple, puis UNE requête GraphQL. Le jeton n'est pas gardé : sans cache, se
    reconnecter à chaque lecture ne coûte qu'un aller-retour, et il n'y a rien à renouveler.

    Le délai est TOTAL : chaque requête reçoit ce qui reste. `trust_env=False` parce que ce
    poste, comme d'autres, pose un proxy HTTP sans `NO_PROXY` : sans cela, une adresse
    interne partirait au proxy et reviendrait en « annuaire injoignable »."""
    with httpx.Client(base_url=adresse.rstrip("/"), trust_env=False,
                      transport=transport) as client:
        r = client.post("/auth/simple/login", timeout=_reste(debut),
                        json={"username": config.ANNUAIRE_COMPTE,
                              "password": config.ANNUAIRE_MOT_DE_PASSE})
        if r.status_code in (401, 403):
            raise _Refus()
        if r.status_code != 200:
            raise _Illisible()
        jeton = r.json()["token"]
        r = client.post("/api/graphql", timeout=_reste(debut),
                        headers={"Authorization": f"Bearer {jeton}"},
                        json={"query": REQUETE, "operationName": "LireAnnuaire"})
        if r.status_code in (401, 403):
            raise _Refus()
        if r.status_code != 200:
            raise _Illisible()
        corps = r.json()
    if corps.get("errors"):
        # LLDAP dit un défaut de DROITS par une erreur GraphQL, avec un statut 200 : c'est ce
        # qu'un compte hors de `lldap_strict_readonly` recevrait.
        raise _Refus()
    return analyser(corps)


def analyser(corps: dict) -> tuple[tuple[CompteAnnuaire, ...], tuple[GroupeAnnuaire, ...]]:
    """La réponse GraphQL (ou la doublure, qui en a la forme) → comptes et groupes, triés.

    Un nom lisible ou un courriel VIDE vaut `None` : LLDAP rend `""` pour un champ non rempli,
    et un écran qui afficherait une chaîne vide croirait avoir un nom."""
    donnees = corps["data"]
    comptes, membres = [], {}
    for u in donnees["users"]:
        login = u["id"]
        if not isinstance(login, str) or not login:
            raise _Illisible()
        noms = tuple(sorted(g["displayName"] for g in (u.get("groups") or [])))
        for nom in noms:
            membres.setdefault(nom, []).append(login)
        comptes.append(CompteAnnuaire(login=login, nom=(u.get("displayName") or None),
                                      courriel=(u.get("email") or None), groupes=noms))
    groupes = {}
    for g in donnees["groups"]:
        nom = g["displayName"]
        if not isinstance(nom, str) or not nom:
            raise _Illisible()
        groupes[nom] = GroupeAnnuaire(id=g.get("id"), nom=nom,
                                      membres=tuple(sorted(membres.get(nom, []))))
    # Un groupe nommé par un compte mais absent de la liste des groupes : la réponse se
    # contredit. On le garde plutôt que de le taire, sans id.
    for nom, logins in membres.items():
        if nom not in groupes:
            groupes[nom] = GroupeAnnuaire(id=None, nom=nom, membres=tuple(sorted(logins)))
    return (tuple(sorted(comptes, key=lambda c: c.login)),
            tuple(sorted(groupes.values(), key=lambda g: g.nom)))


def _lire_doublure(variante: str, lien: Optional[str]) -> Lecture:
    """`doublure:` charge les données fixes ; `doublure:panne` simule un annuaire muet."""
    if variante == "panne":
        return Lecture("non_verifie", source="doublure", motif="delai", lien=lien)
    debut = time.monotonic()
    try:
        comptes, groupes = analyser(json.loads(DOUBLURE.read_text(encoding="utf-8")))
    except (OSError, _Illisible, ValueError, KeyError, TypeError):
        return Lecture("non_verifie", source="doublure", motif="reponse_illisible", lien=lien)
    return Lecture("lu", source="doublure", comptes=comptes, groupes=groupes,
                   lu_le=_maintenant_iso(), duree_ms=int((time.monotonic() - debut) * 1000),
                   lien=lien)


def _maintenant_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
