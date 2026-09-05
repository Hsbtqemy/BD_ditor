---
chantier: QA-6
statut: à venir
---

# QA-6 — un cliquet ÉCHOUE quand le modèle NLP manque, là où le dépôt promet un skip

**Le décor de reproduction est TRIVIAL — 2026-09-05, mesuré.** La fiche laissait croire
qu'il fallait un environnement à part, « spaCy installé et le modèle absent ». Ce n'est
pas nécessaire : `nlp_available()` teste `find_spec(BD_SPACY_MODEL)`, et cette variable
est lue à l'import. Un nom de modèle inexistant suffit, dans le venv ordinaire :

```
BD_SPACY_MODEL=modele_absent pytest tests/test_sorties_identite.py
→ 1 échec (test_les_declarations_ne_mentent_pas), 7 verts
```

C'est exactement le symptôme décrit ci-dessous. La seule contrainte est que la variable
soit posée AVANT le démarrage du processus — `_MODEL` est capturé à l'import du module,
donc un `monkeypatch` en cours de course n'aurait aucun effet, et l'aurait fait passer
pour irreproductible.

**Point de départ** — 2026-09-05, trouvé en vérifiant ARCH-2 dans un venv jetable monté
pour éprouver l'autre forme d'`app.routes`. Aucun code écrit. Le défaut n'a rien à voir
avec ce que ce venv devait mesurer : il est apparu parce que ce venv n'avait pas le modèle
spaCy, configuration que `CLAUDE.md` déclare supportée.

## Reste

### Rendre le cliquet indépendant du moteur, ou l'exempter nommément
- [ ] Sur une instance où `nlp_available()` est False, `tests/test_sorties_identite.py::test_les_declarations_ne_mentent_pas` ne tombe plus — mesuré dans cette configuration, pas seulement sur une machine qui a le modèle
- [ ] Si la réparation passe par le SEMIS (poser une ligne `tokens` pour que la correction semée soit visible sans spaCy) : elle ne DOUBLE pas la ligne que spaCy crée quand il est là, vérifié sur les DEUX configurations
- [ ] Et dans ce cas : les compteurs qui lisent `tokens_effectifs` sont inchangés dans la configuration AVEC modèle — accord modèle↔humain, accord inter, concordance, « % relu » de la relecture
- [ ] Si la réparation passe par une EXEMPTION de la déclaration : le balayage reste exhaustif ailleurs, et l'exemption s'affiche comme celle d'`openpyxl` — un cliquet partiel qui se taît est un cliquet qui rassure à tort

### Chercher les autres du même genre, puisqu'ils viennent par familles
- [ ] La suite entière est passée dans une configuration sans modèle NLP, et le compte est écrit : combien de tests ÉCHOUENT là où le dépôt promet un skip propre ? Seul `test_sorties_identite.py` a été mesuré (1 échec, 7 verts) ; le reste ne l'a pas été
- [ ] Le même passage est fait sans Kumiko, sans les moteurs de bulles/OCR et sans `iiif-prezi3` : `requires_kumiko` / `requires_bulles` / `requires_ocr` couvrent les tests qui appellent le moteur EN DIRECT, pas ceux qui en dépendent par une vue ou un sous-processus

## Contexte

**Le fait.** Dans un venv sans spaCy — `nlp_available()` à False, vérifié — le cliquet des
sorties d'identité échoue ainsi :

```
route /api/regions/{region_id}/tokens déclare ['login'] qu'elle n'émet plus
  — à retirer de la déclaration
```

Ce n'est pas une déclaration périmée : c'est le décor qui a disparu. Le semis d'AUTH-5
insère une ligne dans `token_correction` par SQL direct, avec le login sentinelle en
`auteur`. Mais la vue `tokens_effectifs` — le read model canonique de toutes les surfaces
d'analyse — est construite `FROM tokens t LEFT JOIN token_correction c`
(`database.py:498`). Elle part donc des tokens AUTO, que seul spaCy produit. Sans moteur,
`tokens` est vide, la correction semée n'a pas de ligne de base à rejoindre, la route
n'émet plus rien, et le cliquet conclut que la déclaration mentait.

**Pourquoi ce n'est pas un détail de confort.** C'est exactement la famille du second
constat d'ARCH-2, et ARCH-2 a montré ce que cette famille coûte : l'échec dur sur
`openpyxl` tuait `_balayer_outils` à la quatrième invocation, donc **bien avant** le
plancher `>= 55` posé à la fin du même test — un plancher qui aurait attrapé la panne
FastAPI, et qui n'a pas tiré parce qu'un tableur manquait. Un échec dur sur une dépendance
optionnelle n'est pas un inconfort : c'est un interrupteur en AMONT des gardes. Ici, le
test qui tombe est celui des trois qui contrôle que les listes du cliquet décrivent encore
la réalité.

Et il apprend la mauvaise chose : un rouge fait chercher une régression. `CLAUDE.md` promet
« sans spaCy/modèle, `nlp_available()` est False et tout retombe proprement » — la promesse
porte sur l'application, mais c'est la même attente qu'on a en lançant la suite.

**Les deux réparations ne se valent pas.** Exempter la déclaration quand le moteur manque
est la moins risquée, et la moins bonne : elle retire une surface du balayage, ce qui est
le mode d'échec que ce cliquet combat depuis quatre inventaires ratés. Poser une ligne
`tokens` dans le semis garde le cliquet EXHAUSTIF dans les deux configurations, et c'est la
bonne direction — mais elle touche le semis d'AUTH-5, dont la délicatesse est documentée sur
vingt lignes dans son propre fichier (« le mode d'échec d'un cliquet est son SEMIS, jamais
son balayage »). Le risque précis : une ligne posée là où spaCy en pose déjà une créerait un
doublon sur `(region_id, ordre)`, et les compteurs d'accord, de concordance et de relecture
liraient deux tokens au lieu d'un. C'est pourquoi ce chantier exige la vérification sur les
deux configurations, et non sur celle qui se trouve installée ce jour-là.

**Pourquoi ce n'est pas dans ARCH-2.** Le constat y est né mais son correctif n'y tient
pas : il ne peut pas se vérifier sur la machine de développement, qui a le modèle. Il
demande un environnement avec spaCy et SANS le modèle `fr_core_news_sm` — le
téléchargement du modèle est un geste à part (`python -m spacy download`), donc cette
configuration est facile à produire, mais elle n'existait pas au moment du constat. Livrer
sans elle une modification du semis le plus fragile du dépôt aurait été pire que nommer le
défaut.

**Voisinage.** QA-4 (« le verrou ne couvre que 15 paquets sur 91 ») porte sur ce qui
FLOTTE autour des pins ; celui-ci porte sur ce qui MANQUE légitimement. Rien de commun,
sauf le symptôme : dans les deux cas un test qui ne mesure rien passe pour un test qui
approuve, et QA-4 le dit déjà de son côté — « personne ne l'a vu parce que le test
concerné ne CASSE pas : il se SKIPPE, et un skip se lit comme un succès ». Les deux moitiés
du même piège : un skip qui rassure, un échec qui égare.
