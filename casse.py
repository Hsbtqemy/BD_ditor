"""Normalisation de casse d'une transcription (NLP-3) — logique PURE, sans base.

Le lettrage BD est en CAPITALES : EasyOCR restitue donc « ALORS TINTIN, LE F.B.I.
T'ATTEND À NEW YORK ? ». C'est fidèle et c'est illisible en concordance.

**Ce que fait ce module, et ce qu'il ne fait pas.** Il ne DÉRIVE rien : le numéro
éditorial, les centimètres et le statut de relecture se dérivent parce qu'ils se
CALCULENT ; « TINTIN » → « Tintin » ou « tintin » ne se calcule pas, ça se devine. La
doctrine de la maison pour ce qui se devine n'est pas « dériver à l'affichage », c'est
PRÉ-REMPLIR ET LAISSER CORRIGER. Ce module produit donc une PROPOSITION, que l'humain
voit et retouche avant qu'elle n'entre en base — jamais une transformation appliquée
dans son dos.

Deux appelants, une seule règle : le bouton du mode Transcription (`static/lib/casse.js`)
et l'outil de lot (`tools/normaliser_casse.py`). L'accord des deux implémentations n'est
pas supposé, il est MESURÉ — `tests/cas-casse.json` est lu par `tests/test_casse.py` ET
par `tests/js/casse.test.js`, et toute divergence rend l'une des deux suites rouge.

Cinq règles, et trois d'entre elles sont propres à la bande dessinée.

1. **`only_upper`** — un texte qui n'est pas INTÉGRALEMENT en capitales n'est pas touché
   du tout. C'est la transposition d'`only_empty` de l'OCR : une ligne déjà mixte est
   soit une correction humaine, soit un vrai contraste de lettrage (une lettre manuscrite,
   une coupure de presse, une voix étrangère) — et c'est précisément là que le tout-MAJ
   PORTE du sens. La garde vit dans la fonction et non chez l'appelant : elle rend le
   geste idempotent, donc un second clic ne peut plus démolir « Tintin » en « tintin ».
2. **Un sigle se reconnaît à sa PONCTUATION, jamais à sa casse.** Sur une entrée toute
   en capitales, `FBI` est indiscernable d'un mot ordinaire — aucune heuristique ne les
   sépare, et l'inventer produirait des faux positifs muets. Seule la forme pointée
   `F.B.I.` est certaine, et c'est la seule qu'on préserve. `FBI` redescend donc en bas
   de casse : une erreur qui SE VOIT vaut mieux qu'une erreur qui se cache.
3. **Le saut de ligne ne ferme pas une phrase.** Le lettrage coupe ses lignes pour tenir
   dans la bulle, au milieu des phrases : « JE SUIS\nLÀ » doit donner « Je suis\nlà »
   et non « Je suis\nLà ». C'est l'inverse de la convention d'un texte suivi.
4. **Les points de suspension ne ferment pas une phrase.** Ils marquent l'hésitation
   DANS la réplique bien plus souvent qu'ils ne terminent : « JE... JE NE SAIS PAS »
   donne « Je... je ne sais pas ». Le cas ambigu (« C'EST FINI... ALLONS-Y ») retombe
   donc en bas de casse, visible et corrigeable — cf. règle 2.
5. **Le point qui clôt un sigle ne ferme pas la phrase non plus** : « LE F.B.I. ARRIVE »
   donne « Le F.B.I. arrive », pas « Le F.B.I. Arrive ».

**Les noms propres ne sont PAS relevés**, et c'est un choix et non un manque : les
relever suppose de les connaître, c'est-à-dire le gazetteer d'ANN-3, qui n'est pas
commencé. « tintin » et « new york » sortent d'ici en bas de casse, sous les yeux de qui
vient de cliquer.
"""
from __future__ import annotations

import re

# Un sigle : au moins DEUX groupes « lettre + point » d'affilée, non précédés d'une
# lettre — sans quoi « MONSIEUR.A.B. » se ferait rogner son R. `[^\W\d_]` est la classe
# des lettres Unicode côté Python ; `\p{L}` est son équivalent côté JavaScript (dont le
# `\w` reste ASCII, d'où deux écritures pour une seule règle).
_SIGLE = re.compile(r"(?<![^\W\d_])(?:[^\W\d_]\.){2,}")

# Ce qui FERME une phrase, sous réserve des règles 4 et 5.
_FINALES = ".!?"


def _est_lettre(c: str) -> bool:
    return c.isalpha()


def _est_chiffre(c: str) -> bool:
    # ASCII seulement, et volontairement : `str.isdigit()` accepte les exposants là où
    # `\p{Nd}` les refuse, et cette divergence-là traverserait la table de cas partagée.
    return "0" <= c <= "9"


def est_tout_capitales(texte: str | None) -> bool:
    """Le texte porte-t-il au moins une lettre, toutes en capitales ? (règle `only_upper`)

    Un texte sans aucune lettre (« ?! ») répond False : il n'y a rien à normaliser, et
    le dire ainsi évite à l'appelant d'offrir un geste qui ne ferait rien.
    """
    t = texte or ""
    return any(_est_lettre(c) for c in t) and t == t.upper()


def normaliser(texte: str | None) -> str:
    """Rend la proposition de casse normalisée. Rend le texte INCHANGÉ s'il n'est pas
    intégralement en capitales (règle `only_upper`) — l'appel est donc idempotent."""
    t = texte or ""
    if not est_tout_capitales(t):
        return t

    sigles = {m.start(): m.end() for m in _SIGLE.finditer(t)}
    sortie: list[str] = []
    i, n = 0, len(t)
    majuscule = True                      # début de texte
    while i < n:
        if i in sigles:                   # recopié tel quel ; ses points ne closent rien
            fin = sigles[i]
            sortie.append(t[i:fin])
            majuscule = False
            i = fin
            continue
        c = t[i]
        if c in _FINALES:
            j = i
            while j < n and t[j] == c:
                j += 1
            # Une suite de points est une suspension, pas une fin (règle 4).
            majuscule = not (c == "." and j - i >= 2)
            sortie.append(t[i:j])
            i = j
            continue
        if c == "…":                      # même raison, en un seul signe
            sortie.append(c)
            i += 1
            continue
        if _est_lettre(c) or _est_chiffre(c):
            # La source étant tout en capitales, la forme majuscule EST le caractère lu :
            # on le recopie plutôt que de le remonter, sans aller-retour de casse.
            sortie.append(c if majuscule else c.lower())
            majuscule = False
            i += 1
            continue
        sortie.append(c)                  # ponctuation, espaces, guillemets… : neutres
        i += 1
    return "".join(sortie)
