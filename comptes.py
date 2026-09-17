"""AUTH-6 / AUTH-12 — composer la vue « 👥 Comptes et groupes », et ses signaux.

La vue réunit trois sources qui ne se recouvrent pas : ce que l'ANNUAIRE rend (les comptes et
les groupes qui existent, lus par `annuaire.lire`), ce que l'application a VU (le miroir
`utilisateur` : qui est venu, quand, sous quelle nature) et ce qu'elle a ACCORDÉ
(`collection_acces`). La fusion et le calcul de « À regarder » vivent ICI, à un seul endroit :
l'écran ne les refait pas (accordé le 2026-09-17), sans quoi deux lectures du même état
finiraient par se contredire.

Le format est un contrat avec l'écran, arrêté avec la coordination le 2026-09-17. Sa règle
d'or : un champ que l'on ne peut pas établir vaut `None`, jamais `False` ni `[]` par défaut.
Quand l'annuaire n'a pas répondu, « ce groupe n'a aucun membre » et « je ne sais pas » ne
doivent pas s'écrire pareil — c'est la leçon d'AUTH-8, et celle de `_acces_de` (`None` pour
un groupe, jamais `False`).

Ce module ne décide AUCUN accès. Il lit les accès accordés et le nom des groupes
d'administration (`autorisation.AUTH_ADMIN_GROUPS`, la même source) sans rien fournir en
retour à `autorisation.py`, qui ne l'importe pas.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import autorisation
from annuaire import GROUPES_DE_ROLE, Lecture
from database import NOM_COLLECTION_DEFAUT, collections

# Tranché par Hugo le 2026-09-17 : une reprise d'identité ne s'efface jamais du journal, et un
# mariage laisse la même trace. Sans fenêtre, le signal ne s'éteindrait jamais, et une liste
# qui ne se vide pas apprend à ne plus être lue.
FENETRE_REPRISE_JOURS = 30

# L'ordre de « À regarder » : les accès morts d'abord, parce qu'ils trompent en silence ; les
# arrivants à la fin, parce qu'ils sont nombreux à la rentrée et ne trompent personne.
ORDRE_SIGNAUX = ("groupe_absent", "compte_absent", "proprietaire_absent",
                 "sans_proprietaire", "identite_changee", "jamais_venu")

# Une phrase par état de la lecture : ce que la vue ne sait pas, dit par elle.
LIMITES = {
    "lu": ("Les groupes et leurs membres sont lus dans l'annuaire à l'ouverture de cette vue. "
           "L'accès réel se décide à chaque requête sur ce que le portail transmet, et un "
           "changement fait dans l'annuaire met quelques minutes à y parvenir."),
    "non_verifie": ("L'annuaire n'a pas répondu : on ne sait pas de quels groupes chaque "
                    "compte est membre, donc les accès qu'un compte tient d'un groupe ne sont "
                    "pas montrés, et rien ici ne dit qu'un compte ou un groupe n'existe plus. "
                    "Seuls les accès donnés à un compte en son nom sont complets."),
    "sans_annuaire": ("Les accès accordés par groupe n'apparaissent pas : l'application ne "
                      "connaît que les groupes de la personne qui se connecte, jamais ceux des "
                      "autres. Un compte peut donc tout lire sans figurer ici."),
}


# --------------------------------------------------------------------------- #
# Ce qu'un compte a LAISSÉ — partagé avec `GET /api/comptes` (AUTH-7)
# --------------------------------------------------------------------------- #
def traces(conn) -> tuple[dict, dict, dict]:
    """Les actes, les accès nominatifs et les reprises d'identité, par login.

    Rend `(actes, acces, reprises)` ; `reprises[login] = (nombre, date la plus récente)`.
    Sorti de `routes/collections._comptes` pour que les deux vues comptent la même chose."""
    actes = {r["agent"]: r["n"] for r in conn.execute(
        # Les traces de REPRISE D'IDENTITÉ sont exclues du compte : elles portent bien
        # l'agent, mais ce n'est pas un acte qu'il a posé — c'est un changement observé sur
        # son propre compte. Les compter ferait passer un mariage pour du travail laissé.
        # `utilisateur_nature` aussi (AUTH-6), pour une autre raison : déclarer la nature
        # d'un tiers est bien un acte, mais il n'orpheline aucune annotation, et le verdict
        # répond à « qu'est-ce qu'une suppression orphelinerait ? ».
        "SELECT agent, COUNT(*) AS n FROM evenement "
        "WHERE agent_type = 'humain' AND agent IS NOT NULL "
        "  AND cible_table NOT IN ('utilisateur', 'utilisateur_nature') "
        "GROUP BY agent")}
    acces = {r["principal"]: r["n"] for r in conn.execute(
        "SELECT principal, COUNT(*) AS n FROM collection_acces "
        "WHERE genre = ? GROUP BY principal", (autorisation.UTILISATEUR,))}
    reprises: dict[str, tuple[int, Optional[str]]] = {}
    for r in conn.execute(
            "SELECT avant, date FROM evenement WHERE cible_table = 'utilisateur' ORDER BY id"):
        try:
            login = json.loads(r["avant"] or "{}").get("login")
        except ValueError:                                   # pragma: no cover
            continue
        if login:
            n, derniere = reprises.get(login, (0, None))
            reprises[login] = (n + 1, max(filter(None, (derniere, r["date"])), default=None))
    return actes, acces, reprises


def verdict(n_actes: int, n_acces: int) -> str:
    """Le verdict de départ NOMME tout ce qui serait orphelin, jamais le premier motif trouvé,
    et parle d'une conséquence, jamais d'une recommandation (règle du 2026-09-06)."""
    motifs = [m for m, n in (("des actes", n_actes), ("des accès", n_acces)) if n]
    return ("laisse " + " et ".join(motifs)) if motifs else "rien à orpheliner"


# --------------------------------------------------------------------------- #
# La composition
# --------------------------------------------------------------------------- #
def _iso(date: Optional[str]) -> Optional[str]:
    """Une date SQLite (`AAAA-MM-JJ HH:MM:SS`, UTC) → ISO 8601 avec `Z`, comme `conflit`."""
    if not date:
        return None
    return date if date.endswith("Z") else date.replace(" ", "T") + "Z"


def _cle(nom: Optional[str]) -> str:
    return (nom or "").casefold()


def _recente(date: Optional[str], maintenant: datetime) -> bool:
    if not date:
        return False
    try:
        quand = datetime.strptime(date[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False                    # une date illisible n'allume pas un signal
    return maintenant - quand.replace(tzinfo=timezone.utc) < timedelta(days=FENETRE_REPRISE_JOURS)


def _ordonner(signaux) -> list[str]:
    return sorted(set(signaux), key=ORDRE_SIGNAUX.index)


def composer(conn, lecture: Lecture, *, maintenant: Optional[datetime] = None) -> dict:
    """La réponse de `GET /api/comptes-et-groupes`, selon le format arrêté le 2026-09-17."""
    maintenant = maintenant or datetime.now(timezone.utc)
    lu = lecture.lu
    annu_comptes = {c.login: c for c in lecture.comptes} if lu else {}
    annu_groupes = {g.nom: g for g in lecture.groupes} if lu else {}
    admins = autorisation.AUTH_ADMIN_GROUPS

    utilisateurs = {r["login"]: r for r in conn.execute(
        "SELECT login, nom, email, nature, premiere_vue, derniere_vue FROM utilisateur")}
    cols = {c["id"]: c for c in collections(conn)}
    acces = []
    for r in conn.execute("SELECT collection_id, genre, principal, niveau, exporter "
                          "FROM collection_acces"):
        a = dict(r)
        # DROIT-2 — le droit EFFECTIF, comme `_acces_de` : un propriétaire exporte d'office.
        a["exporter"] = bool(a["exporter"]) or a["niveau"] == autorisation.PROPRIETAIRE
        acces.append(a)
    par_compte, par_groupe = {}, {}
    for a in acces:
        cible = par_compte if a["genre"] == autorisation.UTILISATEUR else par_groupe
        cible.setdefault(a["principal"], []).append(a)
    actes, n_acces, reprises = traces(conn)

    def entree(a, par, groupe=None):
        return {"id": a["collection_id"], "nom": cols[a["collection_id"]]["nom"],
                "niveau": a["niveau"], "exporter": a["exporter"], "par": par,
                "groupe": groupe}

    # ---- Comptes ---------------------------------------------------------- #
    comptes = []
    for login in sorted(set(annu_comptes) | set(utilisateurs) | set(par_compte),
                        key=lambda x: (_cle(x), x)):
        ac, u = annu_comptes.get(login), utilisateurs.get(login)
        groupes = list(ac.groupes) if ac else ([] if lu else None)
        roles = set(groupes or ()) & GROUPES_DE_ROLE
        usage = None
        if lu:
            usage = ("annuaire" if roles and not (set(groupes) - GROUPES_DE_ROLE)
                     else "application")
        lignes = [entree(a, "compte") for a in par_compte.get(login, [])]
        for g in (groupes or ()):
            lignes += [entree(a, "groupe", g) for a in par_groupe.get(g, [])]
        lignes.sort(key=lambda e: (_cle(e["nom"]), e["id"], e["par"] != "compte",
                                   _cle(e["groupe"])))
        n_rep, derniere_reprise = reprises.get(login, (0, None))
        signaux = []
        if lu and ac is None and par_compte.get(login):
            signaux.append("compte_absent")
        if _recente(derniere_reprise, maintenant):
            signaux.append("identite_changee")
        if lu and ac is not None and u is None and usage == "application":
            signaux.append("jamais_venu")
        comptes.append({
            "login": login,
            "nom": (ac.nom if ac and ac.nom else None) or (u["nom"] if u else None),
            "courriel": (ac.courriel if ac and ac.courriel else None) or (u["email"] if u else None),
            "dans_annuaire": (ac is not None) if lu else None,
            "usage": usage,
            "venu": u is not None,
            "premiere_vue": _iso(u["premiere_vue"]) if u else None,
            "derniere_vue": _iso(u["derniere_vue"]) if u else None,
            "nature": u["nature"] if u else None,
            "groupes": groupes,
            "administrateur": bool(set(groupes) & admins) if lu else None,
            "collections": lignes,
            "collections_completes": lu,
            "actes": actes.get(login, 0),
            "acces_explicites": n_acces.get(login, 0),
            "verdict": verdict(actes.get(login, 0), n_acces.get(login, 0)),
            "reprises": n_rep,
            "derniere_reprise": _iso(derniere_reprise),
            "signaux": _ordonner(signaux),
        })

    # ---- Groupes ---------------------------------------------------------- #
    groupes_sortie = []
    for nom in sorted(set(annu_groupes) | set(par_groupe), key=lambda x: (_cle(x), x)):
        ag = annu_groupes.get(nom)
        membres = list(ag.membres) if ag else ([] if lu else None)
        venues = [utilisateurs[m]["derniere_vue"] for m in (membres or ())
                  if m in utilisateurs and utilisateurs[m]["derniere_vue"]]
        lignes = sorted(({"id": a["collection_id"], "nom": cols[a["collection_id"]]["nom"],
                          "niveau": a["niveau"], "exporter": a["exporter"]}
                         for a in par_groupe.get(nom, [])),
                        key=lambda e: (_cle(e["nom"]), e["id"]))
        groupes_sortie.append({
            "id": ag.id if ag else None,
            "nom": nom,
            "dans_annuaire": (ag is not None) if lu else None,
            "role_annuaire": nom in GROUPES_DE_ROLE,
            "administrateur": nom in admins,
            "nb_comptes": len(membres) if membres is not None else None,
            "membres": membres,
            "derniere_venue": _iso(max(venues)) if venues else None,
            "collections": lignes,
            "signaux": ["groupe_absent"] if (lu and ag is None and lignes) else [],
        })

    # ---- Collections ------------------------------------------------------ #
    modifiees = {r["cible_id"]: r["d"] for r in conn.execute(
        # Tranché par Hugo le 2026-09-17 : la description ET les accès. Ranger ou sortir un
        # album ne compte pas — ce n'est pas journalisé, et rien n'y est ajouté.
        "SELECT cible_id, MAX(date) AS d FROM evenement "
        "WHERE (cible_table = 'collection' AND type IN ('creation', 'modification')) "
        "   OR (cible_table = 'collection_acces' AND type IN ('lien', 'delien')) "
        "GROUP BY cible_id")}

    def vivant(a) -> Optional[bool]:
        if not lu:
            return None
        if a["genre"] == autorisation.UTILISATEUR:
            return a["principal"] in annu_comptes
        g = annu_groupes.get(a["principal"])
        return g is not None and bool(g.membres)

    def cle_acces(a):
        return (a["genre"] != autorisation.UTILISATEUR, _cle(a["principal"]), a["principal"])

    collections_sortie = []
    for c in sorted(cols.values(), key=lambda c: (_cle(c["nom"]), c["id"])):
        les_acces = sorted((a for a in acces if a["collection_id"] == c["id"]), key=cle_acces)

        def forme(a, **plus):
            compte = a["genre"] == autorisation.UTILISATEUR
            return {"par": "compte" if compte else "groupe",
                    "login": a["principal"] if compte else None,
                    "groupe": None if compte else a["principal"], **plus}

        proprietaires = [forme(a, vivant=vivant(a)) for a in les_acces
                         if a["niveau"] == autorisation.PROPRIETAIRE]
        repli = c["nom"] == NOM_COLLECTION_DEFAUT
        signaux = []
        if lu and proprietaires and not any(p["vivant"] for p in proprietaires):
            signaux.append("proprietaire_absent")
        # La collection de repli n'a souvent personne à sa tête, et c'est normal : un signal
        # qui ne s'éteint jamais apprend à ignorer la liste (accordé le 2026-09-17).
        if not proprietaires and not repli:
            signaux.append("sans_proprietaire")
        collections_sortie.append({
            "id": c["id"], "nom": c["nom"],
            "nb_albums": c["nb_albums"],
            "statut_diffusion": c["statut_diffusion"],
            "repli": repli,
            "derniere_modification": _iso(modifiees.get(c["id"])),
            "proprietaires": proprietaires,
            "nb_acces": len(les_acces),
            "acces": [forme(a, niveau=a["niveau"], exporter=a["exporter"]) for a in les_acces],
            "signaux": _ordonner(signaux),
        })

    return {
        "annuaire": {"etat": lecture.etat, "source": lecture.source, "lu_le": lecture.lu_le,
                     "duree_ms": lecture.duree_ms, "motif": lecture.motif,
                     "lien": lecture.lien},
        "comptes": comptes,
        "groupes": groupes_sortie,
        "collections": collections_sortie,
        "a_regarder": a_regarder(comptes, groupes_sortie, collections_sortie),
        "limite": LIMITES[lecture.etat],
    }


def a_regarder(comptes: list, groupes: list, collections_sortie: list) -> list:
    """« À regarder », ligne à ligne, ordonné : par code (`ORDRE_SIGNAUX`), puis par nom."""
    noms = {c["id"]: c["nom"] for c in collections_sortie}
    lignes = []
    for g in groupes:
        if "groupe_absent" in g["signaux"]:
            for e in g["collections"]:
                lignes.append(("groupe_absent", g["nom"], noms[e["id"]],
                               {"signal": "groupe_absent", "groupe": g["nom"],
                                "collection": e["id"]}))
    for c in comptes:
        if "compte_absent" in c["signaux"]:
            for e in c["collections"]:
                if e["par"] == "compte":
                    lignes.append(("compte_absent", c["login"], e["nom"],
                                   {"signal": "compte_absent", "login": c["login"],
                                    "collection": e["id"]}))
        for code in ("identite_changee", "jamais_venu"):
            if code in c["signaux"]:
                lignes.append((code, c["login"], "", {"signal": code, "login": c["login"]}))
    for col in collections_sortie:
        for code in ("proprietaire_absent", "sans_proprietaire"):
            if code in col["signaux"]:
                lignes.append((code, col["nom"], "", {"signal": code, "collection": col["id"]}))
    lignes.sort(key=lambda l: (ORDRE_SIGNAUX.index(l[0]), _cle(l[1]), _cle(l[2])))
    return [l[3] for l in lignes]
