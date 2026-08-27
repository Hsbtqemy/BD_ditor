---
chantier: NLP-3
statut: à venir
---

# NLP-3 — normalisation de casse de l'OCR (capitales vers minuscules)

**Point de départ** — le lettrage BD est en CAPITALES, EasyOCR restitue donc du
tout-majuscule (« JE SUIS LÀ ») ; la décision de conception n'est pas tranchée.

## Reste

### Arbitrage
- [ ] L'option retenue est écrite et argumentée dans `docs/` : (a) minuscule simple, (b) re-casing par phrase + majuscule des entités, (c) garder le tout-MAJ fidèle et ne minusculer qu'à l'affichage
- [ ] La question « modifie-t-on le texte STOCKÉ ou seulement l'AFFICHAGE ? » est tranchée explicitement, avec sa réversibilité
- [ ] Le choix « option par album ou réglage global » est tranché

### Mise en œuvre
- [ ] L'OCR pré-remplit en casse normalisée sans jamais écraser une correction humaine (only_empty préservé)
- [ ] Un test couvre un sigle, un nom propre et une majuscule de début de phrase

## Contexte

Tension réelle et documentée : les capitales sont **un trait du médium**, pas un défaut
de saisie. Un minusculage naïf perd les noms propres, la majuscule de phrase et les
sigles ; l'option non destructive (c) est notée comme préférable au backlog.

Ne pas confondre avec le minusculage interne de `pipeline/nlp.py` : celui-là existe déjà
et sert l'analyse spaCy (sans lui, tout le lettrage passerait pour des noms propres). Ici
il s'agit du texte **stocké et affiché** — la transcription.

Recoupe **ANN-3** : restaurer les noms propres suppose de les reconnaître, donc le
gazetteer. Les deux fiches se tiennent.
