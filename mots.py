"""Le découpage en MOTS d'une zone de texte — celui de l'outil, pas celui de spaCy (ANN-7).

Tranché le 2026-10-14 (`docs/grilles-et-releves.md` §5) : un relevé sur des mots désigne les
mots que l'ÉCRAN montre, et il doit exister sans moteur de langue, sans bouger quand le
modèle change. Les `tokens` de spaCy ne conviennent donc pas — absents sans moteur,
régénérés à chaque réindexation, découpés selon un modèle. Ce module découpe, seul, et la
route `GET /api/regions/{id}/mots` rend son découpage (G11 : UN découpage, à un endroit ;
la page Annotation dessine depuis lui, elle ne découpe jamais elle-même).

La règle, et ce qu'elle tranche (la table `tests/cas-mots.json` en est la mesure, cas par
cas ; les cas que la note laissait ouverts y sont marqués « à trancher avec les
linguistes », G11) :

- les espaces et les retours à la ligne séparent ;
- la PONCTUATION forme des mots à elle, et une suite d'un MÊME signe n'en forme qu'un
  (« !!! », « ... ») : l'entrée « emphase par ponctuation » doit pouvoir la désigner. Deux
  signes différents en font deux (« ?! ») ;
- un CLITIQUE ÉLIDÉ se détache avec son apostrophe — `j'`, `m'`, `t'`, `s'`, `l'`, `d'`,
  `n'`, `c'`, `ç'`, `qu'`, et les conjonctions élidées `jusqu'`, `lorsqu'`, `puisqu'`,
  `quoiqu'` —, l'apostrophe typographique comprise ; une apostrophe qui n'élide pas reste
  dans son mot (« aujourd'hui », « presqu'île », « quelqu'un », « p'tit ») ;
- le TRAIT D'UNION reste dans son mot (« peut-être », « dis-moi », « va-t-il ») ;
- la COUPURE de fin de ligne du lettrage (« por-↵trait ») fait UN mot, retour compris ;
- un nombre garde sa virgule ou son point (« 3,50 », « 1.000 »), un sigle pointé ses points
  (« S.N.C.F. »).

Chaque mot porte son RANG (l'indice dans ce découpage), sa FORME (le texte verbatim, tel
qu'il est dans la zone) et sa place (`debut`, `fin` : `texte[debut:fin] == forme`). La
COMPARAISON, elle, se fait sur une clé (`cle`) qui confond les apostrophes, les traits
d'union et la casse : normaliser la casse d'une bulle (NLP-3) ne doit pas désancrer ses
relevés.

Aucune dépendance : ni base, ni moteur. Le module est pur, et sa table se joue sans rien.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

# Les apostrophes qu'on rencontre (la table de `database.cle_tag`, plus la droite).
APOSTROPHES = frozenset("'’‘ʼ‛′")
# Les traits d'union (le tiret court, le trait d'union typographique, l'insécable).
TRAITS = frozenset("-‐‑")
# Les clitiques ÉLIDÉS qui se détachent de ce qui suit, comparés sans casse.
CLITIQUES = frozenset({"j", "m", "t", "s", "l", "d", "n", "c", "ç", "qu",
                       "jusqu", "lorsqu", "puisqu", "quoiqu"})

_SIGLE = re.compile(r"(?:[^\W\d_]\.){2,}")
_CHIFFRE_SUITE = re.compile(r"[.,]\d")
_COUPURE = re.compile(r"[ \t]*\r?\n[ \t]*")
_CLE_APOSTROPHES = str.maketrans({a: "'" for a in APOSTROPHES})
_CLE_TRAITS = str.maketrans({t: "-" for t in TRAITS})


def _lettre(ch: str) -> bool:
    """Un caractère de MOT : une lettre, un chiffre, ou un diacritique combinant."""
    return ch.isalnum() or unicodedata.category(ch).startswith("M")


def _fin_de_mot(texte: str, i: int) -> int:
    """La fin du mot qui commence en `i` (une lettre) : lettres, et apostrophes ou traits
    d'union PRIS entre deux lettres ; un nombre garde sa virgule ou son point ; la coupure de
    fin de ligne (« por-↵trait ») continue le mot."""
    n = len(texte)
    j = i
    while j < n:
        ch = texte[j]
        if _lettre(ch):
            j += 1
            continue
        if ch in APOSTROPHES or ch in TRAITS:
            if j + 1 < n and _lettre(texte[j + 1]):
                j += 1
                continue
            if ch in TRAITS:
                coupure = _COUPURE.match(texte, j + 1)
                if coupure and coupure.end() < n and _lettre(texte[coupure.end()]) \
                        and "\n" in coupure.group(0):
                    j = coupure.end()
                    continue
            break
        if ch in ".," and texte[i:j].isdigit() and _CHIFFRE_SUITE.match(texte, j):
            j += 1
            continue
        break
    return j


def _detacher_clitiques(texte: str, debut: int, fin: int) -> list[tuple[int, int]]:
    """Les morceaux d'un mot une fois ses clitiques élidés détachés (« j'sais » → « j' »,
    « sais » ; « qu'il » → « qu' », « il »). Une apostrophe dont le préfixe n'est pas un
    clitique reste dans le mot (« aujourd'hui »)."""
    morceaux = []
    i = debut
    while i < fin:
        k = i
        while k < fin and texte[k] not in APOSTROPHES:
            k += 1
        if k < fin and k + 1 < fin and texte[i:k].lower() in CLITIQUES:
            morceaux.append((i, k + 1))
            i = k + 1
            continue
        morceaux.append((i, fin))
        break
    return morceaux


def decouper(texte) -> list[dict]:
    """Le découpage de `texte` : `[{"rang", "forme", "debut", "fin"}, …]`, dans l'ordre.
    Un texte vide ou nul n'a aucun mot."""
    texte = texte or ""
    n = len(texte)
    spans: list[tuple[int, int]] = []
    i = 0
    while i < n:
        ch = texte[i]
        if ch.isspace():
            i += 1
            continue
        if _lettre(ch):
            sigle = _SIGLE.match(texte, i)
            if sigle:
                spans.append((i, sigle.end()))
                i = sigle.end()
                continue
            j = _fin_de_mot(texte, i)
            spans.extend(_detacher_clitiques(texte, i, j))
            i = j
            continue
        # Ponctuation (ou symbole) : une suite du MÊME signe ne fait qu'un mot.
        j = i + 1
        while j < n and texte[j] == ch:
            j += 1
        spans.append((i, j))
        i = j
    return [{"rang": r, "forme": texte[d:f], "debut": d, "fin": f}
            for r, (d, f) in enumerate(spans)]


def cle(forme) -> str:
    """La clé de COMPARAISON d'un mot : NFC, apostrophes et traits d'union confondus, la
    coupure de fin de ligne effacée, sans casse. La forme stockée, elle, reste verbatim."""
    s = unicodedata.normalize("NFC", str(forme or ""))
    s = s.translate(_CLE_APOSTROPHES).translate(_CLE_TRAITS)
    s = _COUPURE.sub("", s)
    return s.casefold()


def aligner(ancien, nouveau) -> dict[int, int]:
    """{rang dans `ancien` → rang dans `nouveau`} pour chaque mot RETROUVÉ — même clé, même
    ordre relatif — par l'alignement de séquences (difflib, le patron du ré-ancrage des
    corrections grammaticales). Un mot changé ou disparu n'a pas d'entrée. `ancien` et
    `nouveau` sont des textes."""
    a = [cle(m["forme"]) for m in decouper(ancien)]
    b = [cle(m["forme"]) for m in decouper(nouveau)]
    correspondance = {}
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for a0, b0, taille in sm.get_matching_blocks():
        for k in range(taille):
            correspondance[a0 + k] = b0 + k
    return correspondance
