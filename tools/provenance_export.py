"""Export de provenance — sérialise le journal d'audit (A3) en PROV-O & TEI.

Additif, EN LECTURE SEULE, hors-app (comme les autres `tools/`). Rejoue le journal
append-only (`activite` = runs ; `evenement` = actes atomiques avant/après, cf.
`database.py` et `docs/provenance-audit.md`) vers deux sérialisations standard :

  • PROV-JSON (W3C PROV) — activités, agents, entités et relations
    (`wasGeneratedBy` / `used` / `wasInvalidatedBy` / `wasAssociatedWith` /
    `wasAttributedTo` / `wasInformedBy`) → provenance machine-lisible, réutilisable ;
  • TEI `<revisionDesc>` — un `<change>` par acte (who / when / type / cible) → provenance
    éditoriale, insérable dans l'en-tête TEI d'un export de contenu.

Grain CORPUS : le journal n'est pas re-scopable par album (un acte survit à la suppression
de sa cible). Modèle PRAGMATIQUE : un LOG D'ACTES append-only (chaque `evenement` est une
prov:Activity), non un graphe à versionnement strict d'entités — c'est honnête et suffisant
pour un entrepôt. Le versionnement fin (`wasRevisionOf` entre versions d'entité) reste une
extension possible.

Usage :
    python tools/provenance_export.py                     # PROV-JSON + TEI (JSON) sur stdout
    python tools/provenance_export.py --out-dir prov/     # provenance.json + revisionDesc.xml
La base suit la config du projet (BD_DB_PATH / BD_DATA_DIR).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_PATH, BASE_DIR  # noqa: E402
from _commun import version_outil  # noqa: E402  (provenance de l'outil — paradonnée)

_PREFIXE = {
    "bd": "https://bedediteur.huma-num.fr/prov/",
    "prov": "http://www.w3.org/ns/prov#",
}


def _e(table, cid):
    """Identifiant PROV d'une entité cible (table + id au moment de l'acte)."""
    return f"bd:{table}/{cid}"


def _agent_id(agent):
    return f"bd:agent/{agent}" if agent else None


def prov_json(conn) -> dict:
    """Construit un document PROV-JSON (W3C) depuis le journal. Chaque `activite` (run) et
    chaque `evenement` (acte) devient une prov:Activity ; les cibles sont des entités ; les
    agents (moteurs / humains) portent leur type PROV. Relations : génération, usage,
    invalidation, association/attribution d'agent, information (acte ⟵ run parent)."""
    doc: dict = {"prefix": dict(_PREFIXE), "activity": {}, "agent": {}, "entity": {},
                 "wasGeneratedBy": {}, "used": {}, "wasInvalidatedBy": {},
                 "wasAssociatedWith": {}, "wasAttributedTo": {}, "wasInformedBy": {}}
    agents: dict = {}   # nom -> agent_type (humain|moteur)

    def _voir_agent(nom, atype):
        if nom and nom not in agents:
            agents[nom] = atype

    # 1) Activités (runs ML / sessions).
    for a in conn.execute("SELECT * FROM activite ORDER BY id"):
        aid = f"bd:activite/{a['id']}"
        act = {"prov:type": a["type"], "bd:agent_type": a["agent_type"]}
        if a["version"]:
            act["bd:version"] = a["version"]
        if a["date_debut"]:
            act["prov:startTime"] = a["date_debut"]
        if a["date_fin"]:
            act["prov:endTime"] = a["date_fin"]
        for col in ("params", "portee", "comptes"):
            if a[col]:
                act[f"bd:{col}"] = a[col]
        doc["activity"][aid] = act
        if a["agent"]:
            _voir_agent(a["agent"], a["agent_type"])
            doc["wasAssociatedWith"][f"_:waw_a{a['id']}"] = {
                "prov:activity": aid, "prov:agent": _agent_id(a["agent"])}

    # 2) Événements (actes atomiques) → activités PROV + relations avec la cible.
    for e in conn.execute("SELECT * FROM evenement ORDER BY id"):
        eid = f"bd:evt/{e['id']}"
        ev = {"prov:type": e["type"], "bd:agent_type": e["agent_type"]}
        if e["date"]:
            ev["prov:startTime"] = ev["prov:endTime"] = e["date"]
        doc["activity"][eid] = ev

        ent = _e(e["cible_table"], e["cible_id"])
        doc["entity"].setdefault(ent, {"prov:type": f"bd:{e['cible_table']}"})

        t = e["type"]
        if t == "creation":
            doc["wasGeneratedBy"][f"_:wgb{e['id']}"] = {
                "prov:entity": ent, "prov:activity": eid, "prov:time": e["date"]}
        elif t == "suppression":
            doc["wasInvalidatedBy"][f"_:wib{e['id']}"] = {
                "prov:entity": ent, "prov:activity": eid, "prov:time": e["date"]}
        else:                                     # modification / validation / lien / delien
            doc["used"][f"_:used{e['id']}"] = {
                "prov:entity": ent, "prov:activity": eid, "prov:time": e["date"]}

        if e["agent"]:
            _voir_agent(e["agent"], e["agent_type"])
            doc["wasAssociatedWith"][f"_:waw_e{e['id']}"] = {
                "prov:activity": eid, "prov:agent": _agent_id(e["agent"])}
            doc["wasAttributedTo"][f"_:wat{e['id']}"] = {
                "prov:entity": ent, "prov:agent": _agent_id(e["agent"])}
        if e["activite_id"]:                      # l'acte procède de son run parent
            doc["wasInformedBy"][f"_:winf{e['id']}"] = {
                "prov:informed": eid, "prov:informant": f"bd:activite/{e['activite_id']}"}

    for nom, atype in agents.items():
        doc["agent"][_agent_id(nom)] = {
            "prov:type": "prov:SoftwareAgent" if atype == "moteur" else "prov:Person",
            "bd:nom": nom}
    return doc


def _safe(text):
    """Retire les caractères interdits par XML 1.0 (garde tab/LF/CR)."""
    if text is None:
        return None
    return "".join(c for c in str(text)
                   if ord(c) in (0x09, 0x0A, 0x0D)
                   or 0x20 <= ord(c) <= 0xD7FF or 0xE000 <= ord(c) <= 0xFFFD
                   or ord(c) >= 0x10000)


def tei_revision_desc(conn) -> str:
    """Fragment TEI `<revisionDesc>` : un `<change>` par acte (who / when / type / cible).
    Insérable tel quel dans le `<teiHeader>` d'un export de contenu TEI."""
    root = ET.Element("revisionDesc")
    for e in conn.execute("SELECT * FROM evenement ORDER BY id DESC"):   # plus récent d'abord (usage TEI)
        ch = ET.SubElement(root, "change")
        if e["date"]:
            ch.set("when", _safe(e["date"]))
        if e["agent"]:
            ch.set("who", _safe(f"#{e['agent']}"))
        ch.set("type", _safe(e["type"]))
        ch.set("target", _safe(f"{e['cible_table']}/{e['cible_id']}"))
        ch.text = _safe(f"{e['type']} de {e['cible_table']}/{e['cible_id']}"
                        + (f" par {e['agent']}" if e["agent"] else "")
                        + (" (moteur)" if e["agent_type"] == "moteur" else ""))
    xml = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml


def construire(conn) -> dict:
    """Document complet : PROV-JSON + TEI revisionDesc + résumé (comptes)."""
    prov = prov_json(conn)
    nb_act = conn.execute("SELECT COUNT(*) FROM activite").fetchone()[0]
    nb_evt = conn.execute("SELECT COUNT(*) FROM evenement").fetchone()[0]
    return {"provenance_export": {
        "genere_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "outil": version_outil(BASE_DIR),
        "grain": "corpus · log d'actes append-only (PROV pragmatique)",
        "resume": {"activites": nb_act, "evenements": nb_evt,
                   "agents": len(prov["agent"]), "entites": len(prov["entity"])},
        "prov": prov,
        "tei_revision_desc": tei_revision_desc(conn),
    }}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _connexion_ro():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Export de provenance : journal d'audit → PROV-O (PROV-JSON) & TEI.")
    ap.add_argument("--out-dir", metavar="DIR",
                    help="écrit provenance.json + revisionDesc.xml (défaut : JSON complet sur stdout)")
    args = ap.parse_args(argv)

    try:                      # stdout en UTF-8 même en sous-processus Windows (console cp1252)
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    with _connexion_ro() as conn:
        doc = construire(conn)

    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        with open(os.path.join(args.out_dir, "provenance.json"), "w", encoding="utf-8") as f:
            json.dump(doc["provenance_export"]["prov"], f, ensure_ascii=False, indent=2)
        with open(os.path.join(args.out_dir, "revisionDesc.xml"), "w", encoding="utf-8") as f:
            f.write(doc["provenance_export"]["tei_revision_desc"] + "\n")
        r = doc["provenance_export"]["resume"]
        print(f"PROV-JSON + TEI écrits dans {args.out_dir}/ "
              f"({r['activites']} activités, {r['evenements']} actes)", file=sys.stderr)
    else:
        json.dump(doc, sys.stdout, ensure_ascii=False, indent=2)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
