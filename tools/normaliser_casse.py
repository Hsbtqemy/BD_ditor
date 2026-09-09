"""Normalisation de casse des transcriptions déjà en base, en lot (NLP-3) — CLI.

Mince enveloppe autour de `casse.py`, le cœur partagé avec le bouton du mode
Transcription (`static/lib/casse.js`). Le bouton sert le geste unitaire, sur la bulle
qu'on a sous les yeux ; cet outil sert le RATTRAPAGE — un corpus déjà océrisé compte des
milliers de bulles que personne ne rouvrira une par une.

    python tools/normaliser_casse.py --dry-run            # aperçu, n'écrit rien
    python tools/normaliser_casse.py --album 3            # un album
    python tools/normaliser_casse.py --planche 42         # une planche
    python tools/normaliser_casse.py                      # tout le corpus

**Ce que l'outil NE fait PAS, et c'est le plus important.**

Il ne pose pas `regions.touche`. Cette colonne dit « un humain a corrigé le
pré-remplissage machine », et les indicateurs de dérive la lisent : la poser ici ferait
compter des milliers de corrections qui n'ont jamais eu lieu. La passe est journalisée en
`agent_type='moteur'`, comme une passe ML — ce qu'elle est, une règle déterministe
appliquée par un logiciel. Conséquence voulue : elle est HORS de portée de Ctrl+Z, dont
`undo.py` ne remonte que les actes humains. Ce n'est pas une perte de réversibilité mais
son déplacement, parce que la transformation est réversible PAR CONSTRUCTION tant que la
source était uniformément capitale (`upper(normalisé) == original`, éprouvé par
`tests/test_casse.py`), et parce que `--dry-run` montre avant d'écrire.

Il ne touche pas non plus une ligne qui n'est pas INTÉGRALEMENT en capitales — la garde
`only_upper` vit dans `casse.normaliser` et non ici, si bien qu'aucun appelant ne peut
l'oublier. C'est ce qui rend la passe rejouable sans dégât : relancée, elle ne trouve
plus rien à faire, et surtout elle ne redescend pas les noms propres qu'un humain vient
de relever entre-temps.

La base suit la config du projet (BD_DB_PATH / BD_DATA_DIR).
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import casse  # noqa: E402
import database  # noqa: E402
import journal  # noqa: E402

# Combien d'exemples montrer avant d'écrire. Assez pour juger la règle sur pièces, pas
# assez pour noyer la console d'un corpus entier.
APERCU = 8


def _err(msg=""):
    print(msg, file=sys.stderr)


def candidates(conn, *, album_id=None, planche_id=None) -> list[tuple[int, str, str]]:
    """Les régions à normaliser : (region_id, avant, après), déjà filtrées par `only_upper`.

    Le tri par planche puis par ordre de lecture n'est pas cosmétique : c'est celui de
    l'aperçu, et juger une règle de casse sur des répliques prises dans l'ordre du récit
    est autrement plus parlant qu'un échantillon trié par identifiant.
    """
    ou, params = "", []
    if planche_id is not None:
        ou, params = "AND r.planche_id = ?", [planche_id]
    elif album_id is not None:
        ou, params = "AND p.album_id = ?", [album_id]
    rows = conn.execute(
        f"""SELECT r.id, r.ocr_texte FROM regions r
             JOIN planches p ON p.id = r.planche_id
            WHERE TRIM(COALESCE(r.ocr_texte, '')) <> '' {ou}
            ORDER BY p.numero, p.id, r.ordre, r.id""", params).fetchall()
    trouvees = []
    for r in rows:
        avant = r["ocr_texte"]
        apres = casse.normaliser(avant)
        if apres != avant:                      # `only_upper` a déjà écarté le reste
            trouvees.append((r["id"], avant, apres))
    return trouvees


def _apercu(trouvees) -> None:
    for _, avant, apres in trouvees[:APERCU]:
        _err(f"    - {avant!r}")
        _err(f"    + {apres!r}")
    if len(trouvees) > APERCU:
        _err(f"    … et {len(trouvees) - APERCU} autre(s).")


def appliquer(conn, trouvees, *, portee) -> int:
    """Écrit les normalisations, réindexe le FTS, et journalise la passe (A3).

    L'activité d'ouverture est validée TOUT DE SUITE, pour la même raison que dans
    `database.reindex_all` : les régions sont validées par lots, si bien qu'une panne
    tardive laisse un travail partiel — sans cette trace, le journal ne garderait que
    les passes qui ont abouti, et une passe ratée ne se distinguerait pas d'une passe
    jamais lancée.
    """
    aid = journal.ouvrir_activite(conn, "normalisation_casse", agent="normalisation-casse",
                                  agent_type="moteur", params={"regle": "phrase+sigles"},
                                  portee=portee)
    conn.commit()
    n = 0
    try:
        for region_id, avant, apres in trouvees:
            conn.execute("UPDATE regions SET ocr_texte = ? WHERE id = ?", (apres, region_id))
            # Le texte indexé change : lemmes et tokens doivent suivre, sinon la recherche
            # et l'analyse grammaticale continueraient de porter sur l'ancienne casse.
            database.reindex_region(conn, region_id)
            # PAS de `marquer_touche` : aucun humain n'a corrigé quoi que ce soit ici.
            journal.journaliser(conn, "modification", "regions", region_id,
                                avant={"ocr_texte": avant}, apres={"ocr_texte": apres},
                                agent="normalisation-casse", agent_type="moteur",
                                activite_id=aid)
            n += 1
            if n % 200 == 0:
                conn.commit()
        journal.cloturer_activite(conn, aid, comptes={"regions": n})
        conn.commit()
    except BaseException as exc:
        # `BaseException` comme `database.reindex_all`, et pour sa raison : c'est une CLI
        # qui peut tourner des minutes sur le fil principal, donc Ctrl+C y est
        # l'interruption réaliste — et `KeyboardInterrupt` n'est pas une `Exception`.
        # Sans cette largeur, une passe abandonnée à la main laissait son activité
        # OUVERTE pour toujours, lue comme un run encore en cours.
        interrompu = isinstance(exc, (KeyboardInterrupt, SystemExit))
        # Bilan MINIMAL : `comptes` sort de l'instance dans les exports de provenance, et
        # y verser le message de l'exception enverrait des chemins serveur au dépôt.
        journal.cloturer_activite(
            conn, aid, comptes={"regions": n, "interrompu" if interrompu else "echec": True})
        conn.commit()
        raise
    return n


def main(argv=None) -> int:
    from _commun import forcer_utf8
    forcer_utf8()                                 # Windows : stdout/stderr en UTF-8
    ap = argparse.ArgumentParser(
        description="Normalise la casse des transcriptions déjà en base (capitales du "
                    "lettrage vers la casse de phrase, sigles préservés). Ne touche jamais "
                    "une ligne qui n'est pas intégralement en capitales.")
    cible = ap.add_mutually_exclusive_group()
    cible.add_argument("--album", type=int, help="limiter à un album (id)")
    cible.add_argument("--planche", type=int, help="limiter à une planche (id)")
    ap.add_argument("--dry-run", action="store_true",
                    help="montre ce qui changerait sans rien écrire")
    args = ap.parse_args(argv)

    database.init_db()                            # garantit le schéma (idempotent)
    conn = database.get_connection()
    try:
        trouvees = candidates(conn, album_id=args.album, planche_id=args.planche)
        portee = ({"album_id": args.album} if args.album else
                  {"planche_id": args.planche} if args.planche else {"corpus": True})
        if not trouvees:
            _err("✓ Rien à normaliser : aucune transcription intégralement en capitales.")
            return 0
        _err(f"→ {len(trouvees)} transcription(s) à normaliser :")
        _apercu(trouvees)
        if args.dry_run:
            _err("— APERÇU (--dry-run) : aucune écriture.")
            return 0
        n = appliquer(conn, trouvees, portee=portee)
        _err(f"✓ {n} transcription(s) normalisée(s), réindexée(s), et journalisée(s) "
             f"en acte MACHINE (hors Ctrl+Z, sans marquer les régions « retouchées »).")
        _err("  Les noms propres restent en bas de casse : ils se relèvent à la relecture.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
