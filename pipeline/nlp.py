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
    car inutiles pour la lemmatisation → plus léger et plus rapide).
    À appeler SOUS `_lock` (cf. `lemmatise`) : chargement ET inférence sérialisés."""
    global _nlp
    if _nlp is None:
        import spacy
        _nlp = spacy.load(_MODEL, disable=["parser", "ner"])
    return _nlp


def analyse(text: str) -> tuple[str, list[dict]]:
    """Analyse spaCy en UNE passe → (lemmes, tokens) :
    - lemmes (str) : lemmes des mots de CONTENU (mots-vides exclus), pour l'index FTS
      (recherche par lemme, Palier A) ;
    - tokens (list[dict]) : TOUS les mots (hors espaces/ponctuation) avec
      {ordre, texte, lemme, pos, morph}, pour l'analyse grammaticale (Palier B).
    Renvoie ("", []) si texte vide ou moteur indisponible (repli propre).

    Minuscule avant traitement : crucial pour le lettrage BD en capitales (sinon
    spaCy prend les mots pour des noms propres). Verrou DÉDIÉ (pas jobs.ML_LOCK) :
    sérialise chargement + inférence spaCy (non thread-safe) sans bloquer le chemin
    d'écriture FTS derrière un long job OCR/bulles.
    """
    text = (text or "").strip()
    if not text or not nlp_available():
        return "", []
    try:
        with _lock:
            doc = _get_nlp()(text.lower())
            lemmes, tokens = [], []
            for i, tok in enumerate(doc):
                if tok.is_space or tok.is_punct:
                    continue
                tokens.append({"ordre": i, "texte": tok.text, "lemme": tok.lemma_,
                               "pos": tok.pos_, "morph": str(tok.morph)})
                if tok.is_alpha and not tok.is_stop and len(tok.lemma_) > 1:
                    lemmes.append(tok.lemma_)
            return " ".join(lemmes), tokens
    except Exception:
        # Moteur OPTIONNEL : une panne spaCy ne doit JAMAIS casser indexation /
        # migration / recherche → repli silencieux.
        return "", []


def lemmatise(text: str) -> str:
    """Lemmes des mots de contenu (pour l'index FTS) — raccourci sur `analyse()`."""
    return analyse(text)[0]
