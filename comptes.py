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
from database import NOM_COLLECTION_DEFAUT, SQL_BACS_EFFACES, collections, sql_est_isole

# Tranché par Hugo le 2026-09-17 : une reprise d'identité ne s'efface jamais du journal, et un
# mariage laisse la même trace. Sans fenêtre, le signal ne s'éteindrait jamais, et une liste
# qui ne se vide pas apprend à ne plus être lue.
FENETRE_REPRISE_JOURS = 30

# L'ordre de « À regarder » : les accès morts d'abord, parce qu'ils trompent en silence ; les
# arrivants à la fin, parce qu'ils sont nombreux à la rentrée et ne trompent personne.
# COL-3, tranche 2 — les DEMANDES en tête : quelqu'un attend une réponse, et c'est le seul
# signal qu'une personne a posé exprès. Le rang est un choix de la session, à confirmer.
ORDRE_SIGNAUX = ("demande_en_attente", "groupe_absent", "compte_absent",
                 "proprietaire_absent", "sans_proprietaire", "identite_changee",
                 "jamais_venu")

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
# Ce qu'un compte a LAISSÉ — la règle d'AUTH-7, comptée à un seul endroit
# --------------------------------------------------------------------------- #
def traces(conn) -> tuple[dict, dict, dict, dict]:
    """Les actes, les accès nominatifs, les reprises d'identité et les entrées de projet,
    par login.

    Rend `(actes, acces, reprises, projets)` ; `reprises[login] = (nombre, date la plus
    récente)` ; `projets[login]` : ses lignes à son nom dans `projet_acces` (COL-3, écran
    de la 3a — relecture croisée, défaut 4 : un compte retiré de l'annuaire laissait aussi
    ses entrées de projet, et le verdict ne les comptait pas).
    Sorti de `routes/collections._comptes` pour que les deux vues comptent la même chose."""
    actes = {r["agent"]: r["n"] for r in conn.execute(
        # Les traces de REPRISE D'IDENTITÉ sont exclues du compte : elles portent bien
        # l'agent, mais ce n'est pas un acte qu'il a posé — c'est un changement observé sur
        # son propre compte. Les compter ferait passer un mariage pour du travail laissé.
        # `utilisateur_nature` aussi (AUTH-6), pour une autre raison : déclarer la nature
        # d'un tiers est bien un acte, mais il n'orpheline aucune annotation, et le verdict
        # répond à « qu'est-ce qu'une suppression orphelinerait ? ». La trace d'un Ctrl+Z
        # PASSÉ (`annulation`, AUTH-14) non plus : elle n'a rien produit, et un geste refusé
        # ne doit pas faire passer un compte pour un compte qui a travaillé.
        # `document` et `collection_album` (COL-3, v30) : importer un album, y ajouter un
        # scan, le ranger ou le retirer s'écrivent désormais au journal, et ne comptent pas
        # ici non plus. Ces gestes n'étaient pas comptés la veille, faute d'être écrits ;
        # les compter ferait passer de « rien à orpheliner » à « laisse des actes » un
        # compte qui n'a fait qu'importer, sans que personne l'ait décidé. Qui a importé
        # reste écrit, sur le document.
        # `demande` (COL-3, tranche 2), pour la raison d'`utilisateur_nature` : déposer une
        # demande ou y répondre est un acte, mais il n'orpheline aucune annotation. Qui a
        # demandé reste écrit sur la demande.
        # `tags` (ANN-8) pour la même raison : renommer, fusionner ou supprimer un tag range
        # le vocabulaire, et n'orpheline aucune annotation.
        "SELECT agent, COUNT(*) AS n FROM evenement "
        "WHERE agent_type = 'humain' AND agent IS NOT NULL "
        "  AND cible_table NOT IN ('utilisateur', 'utilisateur_nature', 'annulation', "
        "                          'document', 'collection_album', 'demande', 'tags') "
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
    # COL-4 (S2) — une entrée dans un BAC À SABLE n'est pas une entrée de projet : elle part
    # avec lui chaque lundi, et le verdict de départ ne la compte pas.
    projets = {r["principal"]: r["n"] for r in conn.execute(
        "SELECT principal, COUNT(*) AS n FROM projet_acces "
        f"WHERE genre = ? AND NOT {sql_est_isole('projet_id')} GROUP BY principal",
        (autorisation.UTILISATEUR,))}
    return actes, acces, reprises, projets


def verdict(n_actes: int, n_acces: int, n_projets: int = 0, n_bases: int = 0) -> str:
    """Le verdict de départ NOMME tout ce qui serait orphelin, jamais le premier motif trouvé,
    et parle d'une conséquence, jamais d'une recommandation (règle du 2026-09-06).

    COL-3, écran de la 3a — deux motifs de plus : ses entrées de PROJET, et les collections de
    BASE dont il est le SEUL propriétaire, par le projet (seul responsable, aucune ligne
    explicite) — partir les laisserait sans personne pour décider qui y entre."""
    motifs = [m for m, n in (("des actes", n_actes), ("des accès", n_acces),
                             ("des entrées de projet", n_projets)) if n]
    if n_bases:
        motifs.append("une collection de base sans autre propriétaire" if n_bases == 1
                      else f"{n_bases} collections de base sans autre propriétaire")
    if not motifs:
        return "rien à orpheliner"
    return "laisse " + (motifs[0] if len(motifs) == 1
                        else ", ".join(motifs[:-1]) + " et " + motifs[-1])


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
    # COL-4 (S2, S6) — ni les BACS À SABLE ni le JEU : soixante-quinze bases d'arrivants,
    # chacune « seule propriétaire par le projet », rendraient la vue illisible et ses
    # signaux faux. Un compte dit seulement s'il a un bac à sable (`bac_a_sable`).
    isoles = {r[0] for r in conn.execute(
        "SELECT id FROM projet WHERE bac_a_sable_de IS NOT NULL OR jeu = 1")}
    a_un_bac = {r[0] for r in conn.execute(
        "SELECT bac_a_sable_de FROM projet WHERE bac_a_sable_de IS NOT NULL")}
    cols = {c["id"]: c for c in collections(conn) if c["projet_id"] not in isoles}
    acces = []
    for r in conn.execute("SELECT collection_id, genre, principal, niveau, exporter "
                          "FROM collection_acces"):
        if r["collection_id"] not in cols:
            continue                                # une collection de bac à sable
        a = dict(r)
        # DROIT-2 — le droit EFFECTIF, comme `_acces_de` : un propriétaire exporte d'office.
        a["exporter"] = bool(a["exporter"]) or a["niveau"] == autorisation.PROPRIETAIRE
        acces.append(a)
    par_compte, par_groupe = {}, {}
    for a in acces:
        cible = par_compte if a["genre"] == autorisation.UTILISATEUR else par_groupe
        cible.setdefault(a["principal"], []).append(a)
    # COL-3, écran de la 3a — les accès que le PROJET tient sur sa collection de BASE (D10) :
    # ses responsables propriétaires, ses membres au niveau choisi, DÉRIVÉS par
    # `autorisation.Portee` sans aucune ligne d'accès. La vue les montre comme des accès,
    # marqués « par le projet » (`par_projet`, le nom du projet) : sans eux, la fiche d'un
    # compte disait « aucune collection ne lui est ouverte » à un membre qui écrit dans la
    # base. La règle est `autorisation.acces_derives`, lue ici sans rien décider.
    derives = []
    for c in cols.values():
        if not c.get("base"):
            continue
        for d in autorisation.acces_derives(conn, c["id"]):
            derives.append({"collection_id": c["id"], **d, "par_projet": c.get("projet_nom")})
    derives_compte, derives_groupe = {}, {}
    for a in derives:
        cible = derives_compte if a["genre"] == autorisation.UTILISATEUR else derives_groupe
        cible.setdefault(a["principal"], []).append(a)
    actes, n_acces, reprises, n_projets = traces(conn)
    # Les bases dont un compte est le SEUL propriétaire, par le projet : aucune ligne
    # explicite de propriétaire, et un seul responsable, nommé (pas un groupe).
    bases_seules: dict[str, int] = {}
    for c in cols.values():
        if not c.get("base"):
            continue
        explicites = [a for a in acces if a["collection_id"] == c["id"]
                      and a["niveau"] == autorisation.PROPRIETAIRE]
        responsables = [a for a in derives if a["collection_id"] == c["id"]
                        and a["niveau"] == autorisation.PROPRIETAIRE]
        if (not explicites and len(responsables) == 1
                and responsables[0]["genre"] == autorisation.UTILISATEUR):
            login = responsables[0]["principal"]
            bases_seules[login] = bases_seules.get(login, 0) + 1

    def entree(a, par, groupe=None):
        e = {"id": a["collection_id"], "nom": cols[a["collection_id"]]["nom"],
             "niveau": a["niveau"], "exporter": a["exporter"], "par": par,
             "groupe": groupe}
        if a.get("par_projet") is not None or par == "projet":
            e["par_projet"] = a.get("par_projet")
        return e

    # ---- Comptes ---------------------------------------------------------- #
    comptes = []
    for login in sorted(set(annu_comptes) | set(utilisateurs) | set(par_compte)
                        | set(derives_compte),
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
        lignes += [entree(a, "projet") for a in derives_compte.get(login, [])]
        for g in (groupes or ()):
            lignes += [entree(a, "projet", g) for a in derives_groupe.get(g, [])]
        lignes.sort(key=lambda e: (_cle(e["nom"]), e["id"], e["par"] != "compte",
                                   _cle(e["groupe"])))
        n_rep, derniere_reprise = reprises.get(login, (0, None))
        signaux = []
        # Un compte absent de l'annuaire qui garde un accès À SON NOM — dans une collection,
        # ou une entrée dans un projet (COL-3, écran de la 3a) : la ligne ne s'en va pas avec
        # le compte, et un compte recréé sous ce nom en hériterait.
        if lu and ac is None and (par_compte.get(login) or n_projets.get(login)):
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
            "entrees_projet": n_projets.get(login, 0),
            "verdict": verdict(actes.get(login, 0), n_acces.get(login, 0),
                               n_projets.get(login, 0), bases_seules.get(login, 0)),
            "reprises": n_rep,
            "derniere_reprise": _iso(derniere_reprise),
            "signaux": _ordonner(signaux),
            "bac_a_sable": login in a_un_bac,
        })

    # ---- Groupes ---------------------------------------------------------- #
    groupes_sortie = []
    for nom in sorted(set(annu_groupes) | set(par_groupe) | set(derives_groupe),
                      key=lambda x: (_cle(x), x)):
        ag = annu_groupes.get(nom)
        membres = list(ag.membres) if ag else ([] if lu else None)
        venues = [utilisateurs[m]["derniere_vue"] for m in (membres or ())
                  if m in utilisateurs and utilisateurs[m]["derniere_vue"]]
        lignes = sorted(([{"id": a["collection_id"], "nom": cols[a["collection_id"]]["nom"],
                           "niveau": a["niveau"], "exporter": a["exporter"]}
                          for a in par_groupe.get(nom, [])]
                         + [{"id": a["collection_id"], "nom": cols[a["collection_id"]]["nom"],
                             "niveau": a["niveau"], "exporter": a["exporter"],
                             "par_projet": a["par_projet"]}
                            for a in derives_groupe.get(nom, [])]),
                        key=lambda e: (_cle(e["nom"]), e["id"], "par_projet" in e))
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
        # album ne compte pas. Ce n'était alors pas journalisé ; ça l'est depuis la v30,
        # sous `collection_album`, que cette requête ne lit pas : la décision tient.
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

    # D10 (COL-3, tranche 3) — une collection de BASE a pour propriétaires les responsables
    # de son projet, par DÉRIVATION (`autorisation.Portee`) et sans ligne d'accès : la dire
    # « sans propriétaire » parce qu'aucune ligne ne le dit serait faux dès que le projet a
    # un responsable, et quand il n'en a pas, c'est le PROJET qui est « sans responsable » —
    # la liste des projets le dit déjà (`sans_responsable`). Le signal ne la vise donc
    # jamais, comme il épargne la collection de repli : sinon chaque projet créé ferait
    # apparaître un « accès à régler » dans « À faire » avant même qu'on ait nommé qui en
    # répond.
    bases = {c["id"] for c in cols.values() if c.get("base")}

    collections_sortie = []
    for c in sorted(cols.values(), key=lambda c: (_cle(c["nom"]), c["id"])):
        les_acces = sorted((a for a in acces if a["collection_id"] == c["id"]), key=cle_acces)

        def forme(a, **plus):
            compte = a["genre"] == autorisation.UTILISATEUR
            return {"par": "compte" if compte else "groupe",
                    "login": a["principal"] if compte else None,
                    "groupe": None if compte else a["principal"], **plus}

        les_derives = sorted((a for a in derives if a["collection_id"] == c["id"]),
                             key=cle_acces)
        proprietaires = [forme(a, vivant=vivant(a)) for a in les_acces
                         if a["niveau"] == autorisation.PROPRIETAIRE]
        # Les responsables du projet, propriétaires de sa base par dérivation : ils comptent
        # pour « propriétaire absent » comme les autres, et la vue les dit « par le projet ».
        proprietaires += [forme(a, vivant=vivant(a), par_projet=a["par_projet"])
                          for a in les_derives if a["niveau"] == autorisation.PROPRIETAIRE]
        repli = c["nom"] == NOM_COLLECTION_DEFAUT
        signaux = []
        if lu and proprietaires and not any(p["vivant"] for p in proprietaires):
            signaux.append("proprietaire_absent")
        # La collection de repli n'a souvent personne à sa tête, et c'est normal : un signal
        # qui ne s'éteint jamais apprend à ignorer la liste (accordé le 2026-09-17).
        if not proprietaires and not repli and c["id"] not in bases:
            signaux.append("sans_proprietaire")
        collections_sortie.append({
            "id": c["id"], "nom": c["nom"],
            "nb_albums": c["nb_albums"],
            "statut_diffusion": c["statut_diffusion"],
            "repli": repli,
            "derniere_modification": _iso(modifiees.get(c["id"])),
            "proprietaires": proprietaires,
            "nb_acces": len(les_acces),
            "acces": [forme(a, niveau=a["niveau"], exporter=a["exporter"]) for a in les_acces]
                     + [forme(a, niveau=a["niveau"], exporter=a["exporter"],
                              par_projet=a["par_projet"]) for a in les_derives],
            "signaux": _ordonner(signaux),
        })

    return {
        "annuaire": {"etat": lecture.etat, "source": lecture.source, "lu_le": lecture.lu_le,
                     "duree_ms": lecture.duree_ms, "motif": lecture.motif,
                     "lien": lecture.lien},
        "comptes": comptes,
        "groupes": groupes_sortie,
        "collections": collections_sortie,
        "a_regarder": a_regarder(comptes, groupes_sortie, collections_sortie,
                                 _demandes_en_attente(conn)),
        "limite": LIMITES[lecture.etat],
    }


def _demandes_en_attente(conn) -> list:
    """Les demandes qui attendent une réponse (COL-3, tranche 2), les plus anciennes
    d'abord : `(id, genre)`. Ce que la demande dit — qui, quoi, pourquoi — se lit dans
    `GET /api/demandes` ; « À regarder » ne porte que de quoi y mener."""
    # TOUS les genres (COL-3, écran de la 3a) : « À faire », où mène la ligne, rend chacun
    # avec SES mots et SES boutons — l'entrée de documents, le rejoindre, le retour d'une
    # copie gardée comme les deux suppressions. Le filtre posé par la relecture croisée du
    # serveur de la prise (qui ne laissait passer que les suppressions, faute d'écran pour
    # les autres) est levé avec cet écran. Le genre voyage avec la ligne : l'écran ne dit
    # « suppression » que d'une suppression.
    # COL-4 (S3) — aucune demande d'un bac à sable n'atteint l'administrateur : aucune n'y
    # naît plus (`socle._deposer`), et une demande posée en base n'y paraît pas — y compris
    # une fois le bac à sable effacé, sa ligne de `projet` partie (`SQL_BACS_EFFACES`).
    return [(r[0], r[1]) for r in conn.execute(
        "SELECT id, genre FROM demande WHERE reponse IS NULL "
        f"AND (projet_id IS NULL OR (NOT {sql_est_isole('projet_id')} "
        f"AND projet_id NOT IN ({SQL_BACS_EFFACES}))) ORDER BY id")]


def a_regarder(comptes: list, groupes: list, collections_sortie: list,
               demandes: list = ()) -> list:
    """« À regarder », ligne à ligne, ordonné : par code (`ORDRE_SIGNAUX`), puis par nom.

    Une demande en attente y est une ligne `{"signal": "demande_en_attente", "demande": id,
    "genre": …}`. Sa clé est `demande`, et pas `login` : l'écran mène par défaut tout
    signal qui porte un `login` à la fiche d'un compte (`cibleSignal`), et une demande mène
    au fonds, pas à la personne qui l'a déposée."""
    noms = {c["id"]: c["nom"] for c in collections_sortie}
    lignes = []
    for demande_id, genre in demandes:
        lignes.append(("demande_en_attente", f"{demande_id:09d}", "",
                       {"signal": "demande_en_attente", "demande": demande_id,
                        "genre": genre}))
    for g in groupes:
        if "groupe_absent" in g["signaux"]:
            for e in g["collections"]:
                lignes.append(("groupe_absent", g["nom"], noms[e["id"]],
                               {"signal": "groupe_absent", "groupe": g["nom"],
                                "collection": e["id"]}))
    for c in comptes:
        if "compte_absent" in c["signaux"]:
            avant = len(lignes)
            for e in c["collections"]:
                # À son nom : un accès de collection, ou l'entrée dans une base que son
                # projet lui ouvre (`par: "projet"` sans groupe — COL-3, écran de la 3a).
                if e["par"] == "compte" or (e["par"] == "projet" and not e.get("groupe")):
                    lignes.append(("compte_absent", c["login"], e["nom"],
                                   {"signal": "compte_absent", "login": c["login"],
                                    "collection": e["id"]}))
            if len(lignes) == avant:
                # Une entrée de projet qui n'ouvre rien (base protégée) : la ligne dit le
                # compte, sans collection.
                lignes.append(("compte_absent", c["login"], "",
                               {"signal": "compte_absent", "login": c["login"]}))
        for code in ("identite_changee", "jamais_venu"):
            if code in c["signaux"]:
                lignes.append((code, c["login"], "", {"signal": code, "login": c["login"]}))
    for col in collections_sortie:
        for code in ("proprietaire_absent", "sans_proprietaire"):
            if code in col["signaux"]:
                lignes.append((code, col["nom"], "", {"signal": code, "collection": col["id"]}))
    lignes.sort(key=lambda l: (ORDRE_SIGNAUX.index(l[0]), _cle(l[1]), _cle(l[2])))
    return [l[3] for l in lignes]


# --------------------------------------------------------------------------- #
# Qui entre, vu du PROPRIÉTAIRE d'une collection (AUTH-12, étape 3)
# --------------------------------------------------------------------------- #
# Tranché par Hugo le 2026-09-17 (décision 2 (b), précisée) : le propriétaire voit les NOMS
# des groupes, sans les groupes de rôle de l'annuaire ni ceux des administrateurs, et aucune
# liste des comptes ne lui est servie. Il ne voit ni id, ni
# membres, ni nombre de comptes : la composition d'équipes qui ne sont pas la sienne lui reste
# cachée (UX-4). Les états sont rendus ici, les phrases sont celles de l'écran.
def verifier(lecture: Lecture, genre: str, nom: str) -> str:
    """Un nom existe-t-il dans l'annuaire ? « inconnu » veut dire « n'y existe pas », jamais
    autre chose : la vérification porte donc sur TOUS les comptes et TOUS les groupes, groupes
    de rôle et d'administration compris — les exclure de la LISTE est une question de
    proposition, pas de vérité. La comparaison est EXACTE, comme celle qui ouvre un accès.

    `sans_annuaire` n'est pas `non_verifie` : en mono-poste, dire « l'annuaire ne répond
    pas » affirmerait une panne là où il n'y a pas d'annuaire du tout."""
    if lecture.etat == "sans_annuaire":
        return "sans_annuaire"
    if not lecture.lu:
        return "non_verifie"
    if genre == autorisation.UTILISATEUR:
        existe = any(c.login == nom for c in lecture.comptes)
    else:
        existe = any(g.nom == nom for g in lecture.groupes)
    return "trouve" if existe else "inconnu"


def _groupes_a_proposer(lecture: Lecture) -> Optional[list]:
    """Les NOMS de groupes qu'on propose à qui règle un accès, ou `None` sans annuaire lu."""
    if not lecture.lu:
        return None
    exclus = GROUPES_DE_ROLE | autorisation.AUTH_ADMIN_GROUPS
    return sorted((g.nom for g in lecture.groupes if g.nom not in exclus),
                  key=lambda x: (_cle(x), x))


def _verifications(lecture: Lecture, lignes) -> list:
    """La vérification de principaux DÉJÀ posés (`genre`, `principal`), comptes d'abord."""
    sortie = []
    for r in sorted(lignes, key=lambda r: (r["genre"] != autorisation.UTILISATEUR,
                                           _cle(r["principal"]), r["principal"])):
        compte = r["genre"] == autorisation.UTILISATEUR
        sortie.append({"par": "compte" if compte else "groupe",
                       "login": r["principal"] if compte else None,
                       "groupe": None if compte else r["principal"],
                       "verification": verifier(lecture, r["genre"], r["principal"])})
    return sortie


def choix_des_acces(conn, collection_id: int, lecture: Lecture) -> dict:
    """La réponse de `GET /api/collections/{id}/annuaire` : les groupes à PROPOSER, et la
    vérification des accès déjà accordés sur cette collection (la colonne « Signal »)."""
    lignes = conn.execute("SELECT genre, principal FROM collection_acces "
                          "WHERE collection_id = ?", (collection_id,)).fetchall()
    return {"annuaire": {"etat": lecture.etat, "motif": lecture.motif},
            "groupes": _groupes_a_proposer(lecture),
            "acces": _verifications(lecture, lignes)}


def choix_des_membres(conn, projet_id: int, lecture: Lecture) -> dict:
    """La réponse de `GET /api/projets/{id}/membres/choix` (COL-3) : le jumeau de
    `choix_des_acces`, un étage plus haut — les groupes à PROPOSER au responsable d'un
    projet, et la vérification des membres déjà posés. Mêmes bornes : des NOMS de groupe,
    sans membres ni id, et sans les groupes de rôle ni d'administration."""
    lignes = conn.execute("SELECT genre, principal FROM projet_acces "
                          "WHERE projet_id = ?", (projet_id,)).fetchall()
    return {"annuaire": {"etat": lecture.etat, "motif": lecture.motif},
            "groupes": _groupes_a_proposer(lecture),
            "membres": _verifications(lecture, lignes)}
