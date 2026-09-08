---
chantier: SEC-3
statut: livré
---

# SEC-3 — une dépendance nous retient sous un correctif de sécurité

**Arrêté sur** — 2026-09-08, `d4641de` : **LE VECTEUR EST FERMÉ, LE PLAFOND EST TRANCHÉ, ET
LE BALAYAGE VOIT ENFIN CE QU'IL ÉTAIT VENU CHERCHER.** Les quatre `Image.open` bornent leur
décodage par `formats=PILLOW_FORMATS`, dérivé de la même table que `IMG_EXTS` dans
`config.py` ; le correctif est en production depuis `ec8f442`. 37 tests, 12 mutations.

Le balayage rejoué dans l'image n'a pas fermé sa case, il a montré un second défaut : il
rangeait `<=12.0.0` parmi les conventions de version majeure et masquait donc le plafond
qui l'avait motivé. Corrigé, testé, et le compte du chantier s'en trouve REFAIT — trois des
quatre « plafonds serrés » annoncés la veille sont derrière un `extra` et ne retiennent
personne.

*La précédente version de cette ligne citait `0c89204`, c'est-à-dire le commit d'EXP-1 : le
script qui l'a écrite avait lu `HEAD` avant de commiter le code. Une fiche qui cite le
commit d'un AUTRE chantier ne se voit pas — l'écran ne la dit décalée que sur un commit plus
récent, jamais sur un commit étranger.*

**Point de départ** — trouvé le 2026-09-07 par la passe de revue de QA-4, en posant la
question « qu'est-ce que ce correctif a OUVERT ? » à une descente de version. Aucun test
ne pouvait le voir : les suites vérifient qu'on n'a rien cassé, jamais qu'on n'a rien
laissé ouvert.

## Reste

### Fermer le vecteur, indépendamment des versions
- [x] Les quatre `Image.open()` du dépôt passent `formats=PILLOW_FORMATS`. **Et la passe de mutation a rattrapé une couverture à moitié fictive** : retirer le paramètre des DEUX sites de `pipeline/ocr.py` laissait la suite entièrement verte, alors que le module prétendait couvrir « les quatre »
- [x] Un PSD forgé déposé dans `corpus/` est REFUSÉ à l'ingest (400, et aucun fichier laissé sur disque). Le module établit D'ABORD que le leurre EST un PSD que Pillow ouvrirait sans la garde — sans quoi un test de refus passerait aussi bien sur du bruit
- [x] `config.FORMATS_IMAGE` est la source unique ; `IMG_EXTS` et `PILLOW_FORMATS` en dérivent, et `main.py` importe la première au lieu de la redéfinir. Deux tests gardent les DEUX sens de la divergence — une extension sans format décodable (bénin, ça casse) et un format décodable qu'aucune extension n'apporte (grave, ça élargit)

### Trancher le plafond
- [x] **On GARDE le plafond** (arbitré le 2026-09-08). Le contournement change la question : le vecteur est fermé quelle que soit la version, donc garder `Pillow<=12.0.0` laisse une version en retard et non une brèche ouverte. En face, monter reviendrait à rendre `iiif-prezi3` non installable et à faire re-skipper la conformance IIIF partout — troquer une garde réelle contre un numéro de version
- [x] Condition de réouverture écrite ci-dessous, sur le patron de DROIT-1

### Chercher la forme, pas l'endroit
- [x] La question est posée pour tout le verrou, et elle est REJOUABLE : `tools/plafonds_dependances.py`
- [x] Le balayage est rejoué DANS L'IMAGE, et il y a fallu DEUX corrections plutôt qu'un changement d'environnement. Le venv local ne voit pas `iiif-prezi3` — il le DIT, et c'était la limite prévue (QA-5). Mais la première exécution dans l'image ne montrait pas ce plafond non plus : l'outil rangeait `<=12.0.0` parmi les conventions de version majeure
- [x] Le compte est REFAIT sur ce que les plafonds retiennent vraiment, marqueurs lus : un seul plafond obligatoire fige une release, `Pillow<=12.0.0` par `iiif-prezi3`. Le « motif n'était pas isolé » de la première mesure était faux, et il l'était dans le sens rassurant — cf. ci-dessous
- [x] La règle de classement a sa table de vérité (`tests/test_plafonds_dependances.py`, 25 tests) et sa passe de mutation (6/6 rattrapées). L'outil n'avait aucun test : `tools/` est hors couverture, et un rapport n'a pas de contrat — c'est ce qui a laissé le défaut trois jours

## Contexte

**L'avis.** `CVE-2026-25990` — écriture hors limites au décodage d'une image **PSD**
forgée (tuiles à décalage x ou y négatif). Affecte Pillow **>= 10.3.0**, corrigé dans
**12.1.1** (11 février 2026). Contournement proposé par l'avis lui-même : le paramètre
`formats` d'`Image.open()`, qui empêche d'ouvrir un PSD.

**Pourquoi on ne peut pas simplement monter.** `iiif-prezi3==3.1.1` exige
`Pillow<=12.0.0` en dépendance obligatoire, et il n'y a aucune sortie par le haut :
3.1.1 est la DERNIÈRE version publiée, et son `main` porte encore ce plafond (vérifié le
2026-09-07). QA-4 a redescendu `pillow` de 12.1.0 à 12.0.0 pour rendre la validation IIIF
stricte de nouveau exécutable — **cette descente n'a rien ouvert**, l'ancien pin 12.1.0
étant lui aussi vulnérable. Ce que QA-4 a changé, c'est qu'on ne peut plus monter sans
s'en apercevoir : la borne est désormais écrite dans `requirements-export.txt` et une
garde échoue. C'est un progrès de lisibilité qui rend le blocage VISIBLE, pas un blocage
nouveau.

**Ce qui atténue, et ce qui n'atténue pas.** L'instance est auto-hébergée derrière
Authelia, le corpus est déposé par le chercheur : le vecteur n'est pas ouvert au public.
`pipeline/ingest.py` pose déjà `Image.MAX_IMAGE_PIXELS` (garde anti-bombe de
décompression) — mais c'est une garde d'une AUTRE famille, elle ne dit rien des tuiles
négatives, et la croire suffisante serait l'erreur. **Au 2026-09-07, rien dans le dépôt ne
restreignait les formats** : `Image.open(source)` acceptait tout ce que Pillow sait lire,
alors que le corpus n'est que du TIFF master et du JPEG dérivé. C'est ce que la première
zone du `Reste` a fermé le lendemain ; la phrase est gardée au passé plutôt que corrigée,
parce qu'elle dit POURQUOI ce chantier existe.

**Pourquoi une fiche plutôt qu'un commit dans QA-4.** Le contournement seul tiendrait en
un commit, et la règle serait alors de ne pas ouvrir de fiche. Mais il ne referme pas le
sujet : le plafond, sa condition de réouverture et le balayage des autres paquets sont un
arbitrage, pas une correction. QA-4 est par ailleurs un chantier de DÉPENDANCES — y
glisser une modification de `pipeline/` ferait mentir son périmètre.

## La condition de réouverture du plafond

Sur le patron de la sauvegarde de DROIT-1, dont la condition s'est déclenchée **le
lendemain** de son écriture : une condition qui ne peut pas se déclencher n'en est pas une.

Le plafond se rejoue dès que l'UN de ces trois faits survient.

1. **Un avis vise un format que le corpus accepte VRAIMENT** — TIFF, JPEG, JPEG2000, PNG,
   BMP, GIF, WEBP. Le contournement de `formats` ne protège que de ce qu'on refuse ; sur
   un format qu'on décode, il ne sert à rien et seule la version compte.
2. **`iiif-prezi3` publie une version qui lève le plafond**, ou un remplaçant crédible
   apparaît. Vérifié le 2026-09-07 : `3.1.1` est la dernière publiée et son `main` porte
   encore la contrainte.
3. **Le corpus accueille un format hors de `FORMATS_IMAGE`.** Élargir la table élargit la
   surface de décodage, et l'arbitrage ci-dessus a été rendu sur celle d'aujourd'hui.

## Ce que la garde NE couvre pas, et pourquoi c'est acceptable

Trouvé par la passe de revue du 2026-09-08, en se demandant qui d'autre décode ces
fichiers.

**easyocr est couvert par ricochet** : `pipeline/ocr._open_image` ouvre avec Pillow — donc
borné — puis passe un tableau numpy à `readtext`. Le moteur ne reçoit jamais de chemin et
ne décode rien lui-même.

**Kumiko ne l'est pas** : `pipeline/segmentation` lui passe un CHEMIN, et il décode avec
OpenCV dans un sous-processus, hors de toute garde Pillow. C'est un autre décodeur, donc
un autre corpus d'avis — `formats=` n'y peut rien par construction.

Ce n'est pas une brèche, et l'argument tient en une mesure : **les deux seuls chemins qui
écrivent dans `corpus/` passent par `ingest_image`**, donc par `read_metadata`, donc par la
garde — la route d'upload et l'import ShareDocs, tous deux vérifiés, tous deux effaçant le
master quand l'ingestion refuse. Kumiko ne voit que des fichiers ayant franchi ces sept
formats. Les deux points d'entrée ont chacun leur test, parce qu'ils ont chacun leur
gestion d'erreur : n'en éprouver qu'un ferait reposer l'autre sur la lecture du code.

Le résidu, nommé pour ne pas être redécouvert comme un trou : les masters importés AVANT
ce chantier ont franchi un `Image.open` sans borne, et un fichier déposé à la main sur le
disque par un administrateur n'est passé par aucune garde. `tools/reindex_materiel.py`
relit ces masters, mais il appelle `read_metadata` — il hérite donc de la garde et
refuserait ce que l'ingest refuse aujourd'hui.

## Le balayage masquait ce qu'il était venu chercher (2026-09-08)

Rejoué dans l'image pour fermer la dernière case, il n'a pas fermé la case : il a montré
que **`Pillow<=12.0.0` était rangé parmi les « plafonds de version majeure »**, donc caché
sans `--tous`. Le plafond qui a motivé cet outil était le seul que son rapport ne nommait
pas.

**La cause tient en un mot oublié : l'OPÉRATEUR.** Le classement ne lisait que le numéro
(`MAJEUR = ^\d+(\.0)*$`), et `12.0.0` a la forme d'une borne de majeure. Or `<2.0` exclut
toute la majeure suivante — la convention de l'écosystème, elle ne retient personne sous un
correctif, qui paraît en mineure ou en corrective — tandis que `<=12.0.0` admet cette
release et rien au-dessus. **Le même numéro change de camp selon l'opérateur qui le porte**,
et le `<=` est le plafond le plus serré qui existe. Le commentaire du code disait d'ailleurs
juste — « Ce sont les AUTRES qu'on vient chercher, comme `Pillow<=12.0.0` » : l'intention
était écrite, c'est l'implémentation qui faisait l'inverse.

**Le mode d'échec ne s'annonce jamais.** L'outil sort en 0 quoi qu'il arrive — décision
assumée, un plafond de majeure n'est pas un défaut — donc rien ne bronche ; et une liste
courte de plafonds serrés se lit comme une bonne nouvelle. C'est la forme d'ARCH-2 : non
pas une garde qui tombe, mais **un rapport qui rassure en n'ayant pas regardé**.

**Deux autres défauts sont sortis avec, et ils changent la conclusion du chantier.**

1. **Les marqueurs étaient jetés** (`; extra == "dev"`, `; python_version >= "3.13"`). Une
   borne derrière un extra ne mord que si l'on installe cet extra — la compter comme
   obligatoire annonce un plafond qui ne retient personne. Elle est désormais RAPPORTÉE
   mais MARQUÉE : la masquer serait refaire la faute qu'on vient de réparer, l'outil ne
   pouvant pas deviner quels extras sont posés.
2. **Un extra sur la CIBLE emportait la spécification** : `requests[security]<3.0` était
   coupé au premier `[`, et le plafond disparaissait en silence.

**Le compte refait, marqueurs lus.** `httpx<0.29.0` (starlette) est sous `extra == 'full'`
et `numpy<=2.3.5` (ultralytics) sous deux extras d'export : aucun des deux ne nous retient.
Reste `numpy<2.8` (scipy), obligatoire mais lâche — quatre mineures de marge —, et
**`Pillow<=12.0.0`, seul plafond obligatoire qui fige une release**. La première mesure
concluait « le motif n'était pas isolé » ; c'est faux, et faux dans le sens rassurant.
L'arbitrage du plafond ne bouge pas pour autant : il portait sur Pillow, dont la contrainte
est bien obligatoire (`Pillow<=12.0.0,>=9.1.1`, sans marqueur, vérifié dans l'image aux
côtés de `pydantic` et `requests`).

**Pourquoi il a fallu trois jours.** L'outil n'avait aucun test. `tools/` est hors
couverture (`.coveragerc`), et un rapport n'a pas de contrat qu'une suite puisse vérifier —
alors que sa règle de classement est de la LOGIQUE PURE, justiciable d'une table de vérité,
exactement le critère qui fait entrer un module dans `static/lib/`. Elle en a une
maintenant, et la passe de mutation remet le défaut d'origine en première position.

## Un décodeur qui s'installe tout seul (trouvé le 2026-09-08)

**`ultralytics` remplace `PIL.Image.open` globalement**, au chargement du modèle
(`ultralytics/utils/patches.py` : `Image.open = image_open`). Son enveloppe attrape TOUTE
exception pour appeler `check_requirements("pi-heif")` — donc lancer un `pip install`
depuis le réseau, au milieu d'une requête — puis réessayer.

C'est le contraire exact de ce chantier : on borne les décodeurs, et un tiers en ajoute un
à l'exécution, sur une entrée que l'appelant contrôle. Trois raisons de le défaire, et la
première suffit ; les deux autres se sont vues ici même. Nos refus délibérés ressortaient
en `ModuleNotFoundError: pi_heif` — l'installation échoue toujours dans une image sans
réseau —, ce qui a fait tomber trois tests de ce chantier dès qu'`ultralytics` était
importé. Et le format apporté, HEIC, n'est pas dans `FORMATS_IMAGE` : on paierait un
décodeur de plus pour un format qu'on refuse.

`pipeline/bulles._load_model` capture `Image.open` avant l'import et le restaure après.
On restaure plutôt qu'on empêche : ultralytics décode ses propres images par OpenCV, et
nous ne lui donnons jamais de HEIC. Deux gardes — l'une dit l'ÉTAT (`Image.open` vient de
`PIL`), l'autre que notre code le RÉTABLIT, éprouvée sur une doublure du patch plutôt
qu'en téléchargeant le modèle.

**Pas de fiche pour ce constat** : il est traité dans le même commit, et la règle du
dossier est de ne pas en ouvrir dans ce cas. Il est écrit ici parce que c'est ici qu'on le
cherchera — la question « qu'est-ce qui peut décoder une image dans ce processus ? » est
celle de SEC-3, pas celle du détecteur de bulles.
