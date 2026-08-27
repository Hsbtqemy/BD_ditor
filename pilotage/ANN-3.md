---
chantier: ANN-3
statut: à venir
---

# ANN-3 — gazetteer des noms de personnages (EntityRuler)

**Point de départ** — ANN-2 (entité personnage, v11) est livré ; la reconnaissance des
noms dans le texte OCR reste entièrement manuelle.

## Reste

- [ ] Un gazetteer par album est construit depuis les personnages déjà saisis, et se régénère quand un personnage est ajouté ou fusionné
- [ ] L'EntityRuler spaCy est monté à partir de ce gazetteer sans casser le chargement quand spaCy est absent (`nlp_available()` False → dégradation propre, comme le reste de `pipeline/nlp.py`)
- [ ] Une occurrence d'un nom connu dans un dialogue est signalée à l'annotateur comme suggestion d'attribution de locuteur
- [ ] La suggestion est modifiable et son refus n'est pas réappliqué au reindex suivant
- [ ] Un test couvre le cas « nom présent au gazetteer mais absent du dialogue » (aucune suggestion) et « nom en capitales » (le lettrage BD est en majuscules)

## Contexte

Voie « NER pas cher » pour un cast fermé — le fine-tuning a été écarté faute de données
annotées. Dépend d'ANN-2, qui est fait.

Recoupe **NLP-3** : le lettrage BD arrivant en capitales, un gazetteer naïf ne matchera
rien si la comparaison n'est pas insensible à la casse — et c'est précisément la
normalisation de casse que NLP-3 doit trancher. Les deux fiches gagnent à être traitées
ensemble, ou au moins dans cet ordre.

Priorité P3 au backlog : « au fil du besoin réel ». Rien ne le rend urgent tant qu'ANN-1
n'a pas produit de vraie campagne d'annotation.
