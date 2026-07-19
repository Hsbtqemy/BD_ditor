"""Rapport d'accord modèle↔humain (NLP-1) — cœur partagé.

Mesure, sur les tokens que l'humain a RELUS (une correction active existe), combien de fois le
modèle NLP avait DÉJÀ la valeur finale — par champ (lemme, POS, morpho) — plus une matrice de
confusion POS (ce que l'auto proposait → ce que l'humain a posé). Étalon de la qualité de
l'index (transition Phase 1→2 : mesurer avant/après un passage à `fr_core_news_lg`).

Partagé par la route `GET /api/analyse/accord` et l'outil `tools/rapport_accord.py`.

Grain : `token_correction` ACTIF (obsolete=0) joint à `tokens` (auto) sur (region_id, ordre),
en miroir de la vue `tokens_effectifs`. « Accord » d'un champ = le modèle avait la valeur finale :
correction NULL (auto accepté) OU correction égale à l'auto. Le taux porte sur l'ÉCHANTILLON
RELU (souvent les cas douteux), pas sur tout le corpus — à lire comme tel.
"""
CHAMPS = ("lemme", "pos", "morph")

_BASE = ("FROM token_correction c JOIN tokens t "
         "ON t.region_id = c.region_id AND t.ordre = c.ordre WHERE c.obsolete = 0")


def rapport(conn, confusion_limit: int = 15, album_ids=None) -> dict:
    """Calcule le rapport d'accord (dict sérialisable). `confusion_limit` borne la matrice POS.

    `album_ids` (None = corpus entier) RESTREINT l'échantillon aux tokens dont la région
    appartient à l'un de ces albums — utile pour scoper un export `--collection`. La route et
    l'outil passent None (corpus). Une liste VIDE (collection sans album) → échantillon vide.
    """
    meta = {r["cle"]: r["valeur"] for r in conn.execute(
        "SELECT cle, valeur FROM meta WHERE cle IN ('nlp_model', 'nlp_reindexed_at')")}

    base, params = _BASE, []
    if album_ids is not None:
        if album_ids:
            qm = ",".join("?" * len(album_ids))
            base += (f" AND c.region_id IN (SELECT r.id FROM regions r "
                     f"JOIN planches p ON p.id = r.planche_id WHERE p.album_id IN ({qm}))")
            params = list(album_ids)
        else:
            base += " AND 0"                    # collection sans album → échantillon vide

    acc = ", ".join(f"SUM((c.{ch} IS NULL OR c.{ch} = t.{ch})) AS acc_{ch}" for ch in CHAMPS)
    ligne = conn.execute(
        f"SELECT COUNT(*) AS revus, SUM((c.etat = 'valide')) AS valides, "
        f"       SUM((c.etat = 'corrige')) AS corriges, {acc} {base}", params).fetchone()
    revus = ligne["revus"] or 0
    champs = {}
    for ch in CHAMPS:
        a = ligne[f"acc_{ch}"] or 0
        champs[ch] = {"revus": revus, "accord": a,
                      "taux": round(a / revus, 4) if revus else None}

    # Confusion POS : désaccords où l'humain a posé un POS différent de l'auto (auto NULL = ∅).
    confusion = [dict(r) for r in conn.execute(
        f"SELECT t.pos AS auto, c.pos AS humain, COUNT(*) AS n {base} "
        "AND c.pos IS NOT NULL AND (t.pos IS NULL OR c.pos <> t.pos) "
        "GROUP BY t.pos, c.pos ORDER BY n DESC, humain LIMIT ?", (*params, confusion_limit))]

    return {"modele": meta.get("nlp_model") or None,
            "indexe_le": meta.get("nlp_reindexed_at") or None,
            "revus": revus, "corriges": ligne["corriges"] or 0,
            "valides": ligne["valides"] or 0,
            "champs": champs, "confusion_pos": confusion}
