"""Lemmatisation (spaCy) pour la recherche — moteur OPTIONNEL.

Objectif (Palier A) : indexer les LEMMES des textes (OCR corrigé + note) pour que
« otage » trouve « otages », « obéir » trouve « obéissait », etc. — ce que le
préfixe + accents ne couvre pas (pluriel↔singulier, conjugaisons, élisions).

Conception :
- Moteur optionnel : sans spaCy/modèle installé, `nlp_available()` est False et
  `lemmatise()` renvoie "" → la recherche retombe proprement sur le préfixe+accents.
- Modèle CONFIGURABLE via BD_SPACY_MODEL (défaut `fr_core_news_sm`, léger ; on peut
  passer à `fr_core_news_lg` le jour où la RAM le permet, sans changer le code).
- MINUSCULE avant traitement : le lettrage BD est en capitales, ce qui fait prendre
  les mots pour des noms propres (non lemmatisés). Minusculer corrige ça.
- Chargement paresseux + verrou : spaCy n'est pas garanti thread-safe, et le modèle
  ne se charge qu'au premier usage (≈ quelques secondes), puis ≈ 15 ms / texte.
"""
from __future__ import annotations

import importlib.util
import os
import threading

_MODEL = os.environ.get("BD_SPACY_MODEL", "fr_core_news_sm")
_nlp = None
_lock = threading.Lock()


def nlp_available() -> bool:
    """spaCy ET le modèle configuré sont-ils installés ?"""
    return (importlib.util.find_spec("spacy") is not None
            and importlib.util.find_spec(_MODEL) is not None)


def _get_nlp():
    """Charge le modèle une seule fois (tagger + lemmatizer ; parser/NER désactivés
    car inutiles pour la lemmatisation → plus léger et plus rapide)."""
    global _nlp
    with _lock:
        if _nlp is None:
            import spacy
            _nlp = spacy.load(_MODEL, disable=["parser", "ner"])
        return _nlp


def lemmatise(text: str) -> str:
    """Lemmes (minuscules) des mots de contenu, séparés par des espaces — prêts pour
    l'index FTS. Renvoie "" si texte vide ou moteur indisponible (→ repli recherche)."""
    text = (text or "").strip()
    if not text or not nlp_available():
        return ""
    try:
        doc = _get_nlp()(text.lower())   # minuscule : crucial pour le lettrage BD en capitales
        return " ".join(
            tok.lemma_ for tok in doc
            if tok.is_alpha and not tok.is_stop and len(tok.lemma_) > 1
        )
    except Exception:
        # Moteur OPTIONNEL : une panne spaCy (modèle corrompu…) ne doit JAMAIS
        # casser l'indexation, la migration ou la recherche → repli silencieux.
        return ""
