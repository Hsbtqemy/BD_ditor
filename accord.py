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

NLP-2 (v28) — ce que l'annotateur a VU. Un champ de correction NULL veut dire « j'accepte la
proposition du modèle ». Jusqu'à la v28, cette proposition se relisait dans `tokens`, que
chaque réindexation régénère : après un passage à `lg`, un mot validé sous `sm` comptait comme
un accord avec `lg`, dont personne n'avait vu la proposition. La correction garde désormais la
proposition affichée (`auto_*`) et le modèle qui l'a faite (`modele_auto`). La vérité humaine
d'un champ est donc la valeur posée, sinon la proposition VUE — sinon, pour une correction
antérieure à la v28 qui n'a rien gardé, l'auto d'aujourd'hui : la lecture d'avant, bornée à
ces lignes, et `par_modele` en dit la part.

Deux mesures, pour deux questions :
- `champs` : l'index ACTUEL (`meta.nlp_model`) retrouve-t-il la vérité humaine ? Tant que le
  modèle n'a pas changé, le résultat est celui d'avant la v28.
- `a_la_relecture` (avec `modele` seulement) : le modèle relu avait-il raison AU MOMENT où
  l'humain l'a regardé ? Cette mesure ne lit pas `tokens`.
Après un passage à `lg`, `rapport(modele=<sm>)` donne donc `sm` et `lg` sur les MÊMES
relectures : la comparaison que ce rapport existe pour permettre.
"""
CHAMPS = ("lemme", "pos", "morph")

_BASE = ("FROM token_correction c JOIN tokens t "
         "ON t.region_id = c.region_id AND t.ordre = c.ordre WHERE c.obsolete = 0")


def _index(ch):
    """La proposition de l'index actuel."""
    return f"t.{ch}"


def _vu(ch):
    """Ce que l'annotateur a vu : la proposition gardée (v28), sinon l'auto d'aujourd'hui."""
    return f"COALESCE(c.auto_{ch}, t.{ch})"


def _humain(ch):
    """La vérité humaine : la valeur posée, sinon la proposition vue — et donc acceptée."""
    return f"COALESCE(c.{ch}, {_vu(ch)})"


def _egal(a, b):
    """Égalité où « rien » vaut « rien » : spaCy écrit '' pour une morpho vide, un relevé ''
    pour une proposition absente, et un token semé à la main NULL. Rend 0 ou 1, jamais NULL."""
    return f"(NULLIF({a}, '') IS NULLIF({b}, ''))"


def _mesure(conn, base, params, revus, proposition, confusion_limit):
    """Accord par champ, et confusion POS, entre la vérité humaine et `proposition(ch)` —
    l'expression SQL de ce qu'on évalue."""
    acc = ", ".join(f"SUM({_egal(_humain(ch), proposition(ch))}) AS acc_{ch}"
                    for ch in CHAMPS)
    ligne = conn.execute(f"SELECT {acc} {base}", params).fetchone()
    champs = {}
    for ch in CHAMPS:
        a = ligne[f"acc_{ch}"] or 0
        champs[ch] = {"revus": revus, "accord": a,
                      "taux": round(a / revus, 4) if revus else None}

    # Confusion POS : ce que la proposition disait → ce que l'humain tient pour vrai, quand ils
    # diffèrent (proposition vide = ∅). Une vérité humaine VIDE n'y figure pas : la matrice
    # dit quel POS l'humain a mis à la place, et « aucun » n'en est pas un.
    h, p = _humain("pos"), proposition("pos")
    confusion = [dict(r) for r in conn.execute(
        f"SELECT NULLIF({p}, '') AS auto, {h} AS humain, COUNT(*) AS n {base} "
        f"AND NULLIF({h}, '') IS NOT NULL AND NOT {_egal(h, p)} "
        "GROUP BY 1, 2 ORDER BY n DESC, humain LIMIT ?", (*params, confusion_limit))]
    return champs, confusion


def rapport(conn, confusion_limit: int = 15, album_ids=None, modele=None) -> dict:
    """Calcule le rapport d'accord (dict sérialisable). `confusion_limit` borne la matrice POS.

    `album_ids` (None = corpus entier) RESTREINT l'échantillon aux tokens dont la région
    appartient à l'un de ces albums — utile pour scoper un export `--collection`. La route et
    l'outil passent None (corpus). Une liste VIDE (collection sans album) → échantillon vide.

    `modele` (NLP-2) restreint l'échantillon aux relectures faites sur la sortie de ce modèle
    (`token_correction.modele_auto`), et ajoute la mesure `a_la_relecture`. `par_modele`, lui,
    ignore ce filtre : il décrit l'échantillon entier, pour qu'on voie de quoi il est mêlé.
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

    par_modele = [{"modele": r["modele"], "revus": r["n"]} for r in conn.execute(
        f"SELECT c.modele_auto AS modele, COUNT(*) AS n {base} "
        "GROUP BY c.modele_auto ORDER BY n DESC, modele", params)]
    if modele is not None:
        base += " AND c.modele_auto = ?"
        params = [*params, modele]

    ligne = conn.execute(
        f"SELECT COUNT(*) AS revus, SUM((c.etat = 'valide')) AS valides, "
        f"       SUM((c.etat = 'corrige')) AS corriges {base}", params).fetchone()
    revus = ligne["revus"] or 0
    champs, confusion = _mesure(conn, base, params, revus, _index, confusion_limit)

    a_la_relecture = None
    if modele is not None:
        ch_vu, conf_vu = _mesure(conn, base, params, revus, _vu, confusion_limit)
        a_la_relecture = {"modele": modele, "champs": ch_vu, "confusion_pos": conf_vu}

    return {"modele": meta.get("nlp_model") or None,
            "indexe_le": meta.get("nlp_reindexed_at") or None,
            "revus": revus, "corriges": ligne["corriges"] or 0,
            "valides": ligne["valides"] or 0,
            "champs": champs, "confusion_pos": confusion,
            "par_modele": par_modele, "filtre_modele": modele,
            "a_la_relecture": a_la_relecture}
