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


def est_charge() -> bool:
    """Le modèle spaCy est-il résident en mémoire ? (CONC-2.)"""
    return _nlp is not None


def liberer() -> bool:
    """Décharge le modèle spaCy résident (libère la RAM) ; True si qqch a été libéré.
    Sous `_lock` (cohérent avec le chargement/inférence, non thread-safe)."""
    global _nlp
    with _lock:
        libere = _nlp is not None
        _nlp = None
    return libere


def _extract(doc) -> tuple[str, list[dict]]:
    """D'un Doc spaCy → (lemmes, tokens). Factorisé pour `analyse` ET `analyse_batch`
    (garantit un résultat unitaire == lot).
    - lemmes (str) : lemmes des mots de CONTENU (mots-vides exclus) → index FTS (A) ;
    - tokens (list) : TOUS les mots (hors espaces/ponctuation) {ordre,texte,lemme,
      pos,morph} → analyse grammaticale (B)."""
    lemmes, tokens = [], []
    for i, tok in enumerate(doc):
        if tok.is_space or tok.is_punct:
            continue
        tokens.append({"ordre": i, "texte": tok.text, "lemme": tok.lemma_,
                       "pos": tok.pos_, "morph": str(tok.morph)})
        if tok.is_alpha and not tok.is_stop and len(tok.lemma_) > 1:
            lemmes.append(tok.lemma_)
    return " ".join(lemmes), tokens


def analyse(text: str) -> tuple[str, list[dict]]:
    """Analyse spaCy d'UN texte → (lemmes, tokens). Minuscule avant traitement
    (lettrage BD en capitales). Verrou DÉDIÉ (pas jobs.ML_LOCK) : sérialise
    chargement + inférence (non thread-safe) sans bloquer le chemin FTS derrière un
    job OCR. ("", []) si vide ou moteur indisponible (repli propre)."""
    text = (text or "").strip()
    if not text or not nlp_available():
        return "", []
    try:
        with _lock:
            return _extract(_get_nlp()(text.lower()))
    except Exception:
        return "", []   # moteur OPTIONNEL : ne JAMAIS casser indexation/recherche


def analyse_batch(texts) -> list[tuple[str, list[dict]]]:
    """Comme `analyse()` mais en LOT via `nlp.pipe` (réindexation massive) :
    beaucoup plus rapide sur de nombreux textes courts, et une seule prise de verrou.
    Renvoie une liste alignée sur `texts` ; [("", []), …] si moteur indisponible."""
    texts = list(texts)
    if not nlp_available():
        return [("", []) for _ in texts]
    try:
        with _lock:
            return [_extract(doc) for doc
                    in _get_nlp().pipe([(t or "").lower() for t in texts], batch_size=64)]
    except Exception:
        return [("", []) for _ in texts]


def configured_model() -> str:
    """Nom du modèle configuré (BD_SPACY_MODEL) — SANS charger spaCy (info légère)."""
    return _MODEL


def model_info() -> dict:
    """Identité du modèle (reproductibilité de l'index) : {model, spacy} ou {}.
    ⚠ CHARGE le modèle (à n'appeler que quand on l'utilise déjà, p.ex. reindex_all) —
    pour une info légère sans chargement, voir `configured_model()`."""
    if not nlp_available():
        return {}
    try:
        with _lock:
            m = _get_nlp().meta
        import spacy
        return {"model": f"{m['lang']}_{m['name']}-{m['version']}", "spacy": spacy.__version__}
    except Exception:
        return {}


def lemmatise(text: str) -> str:
    """Lemmes des mots de contenu (pour l'index FTS) — raccourci sur `analyse()`."""
    return analyse(text)[0]


def ensure_loaded() -> None:
    """Charge le modèle MAINTENANT (synchrone), s'il est disponible. À appeler HORS
    d'une transaction d'écriture SQLite : sinon le chargement à froid (~10 s) se ferait
    le verrou DB tenu, refusant toute écriture concurrente (409). No-op si déjà chargé
    ou moteur indisponible."""
    if not nlp_available():
        return
    try:
        with _lock:
            _get_nlp()
    except Exception:
        pass


def prewarm() -> None:
    """Charge le modèle en ARRIÈRE-PLAN (thread démon), pour éviter que la PREMIÈRE
    écriture ou recherche ne paie le chargement à froid (~10 s) en pleine requête —
    utile en déploiement multi-utilisateurs. Ne bloque pas le démarrage ; sans effet
    si le moteur est indisponible. Optionnel (cf. BD_NLP_PREWARM) afin de préserver le
    démarrage instantané et la légèreté quand le NLP n'est pas utilisé."""
    if not nlp_available():
        return

    def _load():
        try:
            with _lock:
                _get_nlp()
        except Exception:
            pass

    threading.Thread(target=_load, name="nlp-prewarm", daemon=True).start()
