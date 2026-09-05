---
chantier: QA-6
statut: clos
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

**Arrêté sur** — passe de revue : une quatrième configuration (noyau seul sans
`openpyxl`), le bord non mesuré nommé (`e2e`), et le commentaire du semis dit enfin
pourquoi lui seul a besoin d'une garde conditionnelle ; commit `4dde1af`, 5 septembre.
Le correctif lui-même est au commit `e90f50f`.

**Point de départ** — 2026-09-05, trouvé en vérifiant ARCH-2 dans un venv jetable monté
pour éprouver l'autre forme d'`app.routes`. Aucun code écrit. Le défaut n'a rien à voir
avec ce que ce venv devait mesurer : il est apparu parce que ce venv n'avait pas le modèle
spaCy, configuration que `CLAUDE.md` déclare supportée.

## Reste

### Rendre le cliquet indépendant du moteur, ou l'exempter nommément
- [x] Sur une instance où `nlp_available()` est False, `tests/test_sorties_identite.py::test_les_declarations_ne_mentent_pas` ne tombe plus — mesuré dans cette configuration, pas seulement sur une machine qui a le modèle
- [x] Réparation par le SEMIS, pas par l'exemption : il pose la ligne `tokens` sous sa correction, et il ne DOUBLE pas celle que spaCy crée quand il est là — vérifié sur les DEUX configurations, et tenu par `test_le_semis_ne_double_pas_le_token`
- [x] Les compteurs qui lisent `tokens_effectifs` sont inchangés dans la configuration AVEC modèle — accord modèle↔humain, accord inter, concordance, « % relu » de la relecture : 683 verts sur 684, le seul skip étant `iiif-prezi3`

### Chercher les autres du même genre, puisqu'ils viennent par familles
- [x] La suite entière est passée dans une configuration sans modèle NLP, et le compte est écrit : **1 seul** test ÉCHOUAIT là où le dépôt promet un skip propre, celui du constat lui-même — 684 tests, 675 verts, 9 skips, 0 échec après réparation
- [x] Le même passage est fait sans Kumiko, sans les moteurs de bulles/OCR et sans `iiif-prezi3` : **2 échecs de plus**, `test_sante.py` important `cv2` sans garde — 684 tests, 652 verts, 32 skips, 0 échec après réparation
- [x] Et sans `openpyxl`, que le venv nu portait encore : 649 verts, 35 skips, 0 échec, et le cliquet ANNONCE son balayage partiel en nommant les deux surfaces XLSX qu'il n'a pas regardées — la réparation d'ARCH-2 était crue, elle est mesurée

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

---

## Ce qui a été fait — 2026-09-05

**Le semis, pas l'exemption, et la fiche disait déjà pourquoi.** Exempter la déclaration
quand le moteur manque retirait une surface du balayage — le mode d'échec exact que ce
cliquet combat depuis quatre inventaires ratés. Le semis d'AUTH-5 pose donc lui-même le
token AUTO sous sa correction, par un `INSERT … SELECT … WHERE NOT EXISTS` : spaCy le pose
quand le modèle est là, le semis quand il ne l'est pas, jamais les deux.

Le risque annoncé — le doublon sur `(region_id, ordre)` — est réel et SILENCIEUX : la
table n'a aucune unicité là-dessus, rien ne lèverait, et l'accord, la concordance et le
« % relu » compteraient deux tokens pour un. Il est désormais tenu par un test qui vérifie
le COMPTE plutôt que de le laisser à la lecture du SQL, et la garde a été éprouvée par
mutation : sans le `WHERE NOT EXISTS`, elle tombe sur `2 == 1` dans la configuration avec
modèle.

**La famille existait bien.** Deux tests de `test_sante.py` faisaient `import cv2` nu et
ÉCHOUAIENT sur une installation noyau. Ils sont gardés SÉPARÉMENT, et c'est la seule
finesse du correctif : celui qui truque la version n'a besoin QUE de cv2
(`pytest.importorskip`), celui dont l'attendu est `ok is True` exige en plus le clone
`lib/kumiko` (`requires_kumiko`). Leur donner le même marqueur aurait ajouté un skip
inutile — et QA-4 le dit de son côté, « un skip se lit comme un succès ».

**Les quatre configurations.** La suite en compte 684 après le chantier, 683 avant — il
ajoute un test.

| configuration | avant | après |
|---|---|---|
| avec modèle (venv de développement) | le défaut ne s'y manifeste pas | 683 verts, 1 skip, **0 échec** |
| spaCy sans son modèle (`BD_SPACY_MODEL=modele_absent`) | **1 échec** | 675 verts, 9 skips, **0 échec** |
| noyau seul (venv nu depuis `requirements-dev.lock`, moteurs désinstallés) | **2 échecs** | 652 verts, 32 skips, **0 échec** |
| le même, sans `openpyxl` | — | 649 verts, 35 skips, **0 échec** |

La première ligne n'a pas de « avant » chiffré, et c'est exact : sur la machine qui a le
modèle, aucune de ces trois pannes ne se produit — c'est tout le sujet du chantier. Ce
qu'il fallait prouver de ce côté n'est pas un compte mais une NON-VARIATION, et elle l'est
autrement : l'insertion est un no-op quand spaCy a posé sa ligne, `test_le_semis_ne_double_pas_le_token`
le vérifie, et la mutation le confirme en rougissant à `2 == 1`. Le tableau portait
d'abord « 683 verts, 1 skip » dans cette case — un chiffre jamais mesuré, et faux d'une
unité puisque la suite en comptait 683 avant le test ajouté.

La troisième mérite sa note : le verrou runtime installe les moteurs (`ultralytics`,
`easyocr`, `spacy`, `opencv`), si bien qu'un venv monté depuis `requirements-dev.lock`
n'est PAS une installation noyau — il a fallu les désinstaller ensuite. C'est le décor
qu'obtient qui suit `pip install -r requirements.txt`, et il n'était jamais mesuré.

**La reproduction ne demandait pas le second environnement, la recherche si.** Le premier
défaut se rejouait dans le venv ordinaire avec une variable ; les deux autres non — ils
supposaient l'absence de `cv2`, qu'aucune variable ne simule honnêtement (bloquer un
import par un `meta_path` fait LEVER `find_spec` là où une vraie absence rend `None`, donc
`ocr_available()` explose au lieu de répondre `False` — le simulacre mesure autre chose).

**Une affirmation périmée trouvée en passant.** La docstring de `sante.py` affirmait
« une image sans spaCy passe la suite à 100 % vert (mesuré, cf. `pilotage/QA-5.md`) ».
C'était vrai au moment de la mesure et faux depuis, sans que rien ne le dise — la phrase
porte maintenant sa propre contradiction et la date de la remesure. La dégradation propre
n'est pas une propriété acquise : c'est une propriété qui se REMESURE.

**Ce qui n'a PAS été mesuré, et il faut que ce soit écrit.**

- **Le marqueur `e2e`**, exclu par défaut de la suite (`pytest.ini`), n'a été joué dans
  aucune de ces configurations : elles n'ont pas de Chromium installé. Les imports y sont
  propres — le balayage de la forme `import <moteur>` couvre `tests/*.py` en entier, e2e
  compris, et n'a rien trouvé d'autre que les deux de `test_sante.py` — mais une dépendance
  d'exécution y resterait invisible.
- **L'autre moitié du piège.** Ce chantier a compté les tests qui ÉCHOUENT sans moteur ; il
  n'a pas cherché ceux qui PASSENT en ne mesurant plus rien. Les deux se ressemblent de
  loin et QA-4 nomme déjà le second. Ce qu'on peut dire sans l'avoir cherché : six fichiers
  sèment `tokens` par SQL direct plutôt que de compter sur spaCy (`test_accord`,
  `test_analyse`, `test_autorisation`, `test_export_metadonnees`, `test_infra2_auteur`,
  `test_regressions`, `test_relecture`), donc leurs assertions ne se vident pas avec le
  moteur. Le semis d'AUTH-5 était l'exception, et il rentre dans le rang. Ce n'est pas une
  preuve d'absence.

**Ce que la passe de revue a trouvé, sur une suite verte des trois côtés.** Une mesure
manquante (`openpyxl`, encore installé dans le venv « nu » — la configuration disait
davantage qu'elle ne montrait), un chiffre du tableau ci-dessus jamais mesuré, et un
commentaire qui décrivait la garde sans dire pourquoi elle est nécessaire ICI et nulle
part ailleurs. Aucune ne serait sortie d'un test.
