---
chantier: SEC-3
statut: interrompu
---

# SEC-3 — une dépendance nous retient sous un correctif de sécurité

**Arrêté sur** — 2026-09-08, `0c89204` : **LE VECTEUR EST FERMÉ, LE PLAFOND EST TRANCHÉ, ET
LE BALAYAGE A TROUVÉ AUTRE CHOSE.** Les quatre `Image.open` bornent leur décodage par
`formats=PILLOW_FORMATS`, dérivé de la même table que `IMG_EXTS` dans `config.py`. Onze
tests, six mutations. Reste à rejouer le balayage des plafonds dans l'IMAGE, où
`iiif-prezi3` est réellement installé.

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
- [x] La question est posée pour tout le verrou, et elle est REJOUABLE : `tools/plafonds_dependances.py`. Quatre plafonds serrés trouvés — dont `ultralytics` qui retient `numpy<=2.3.5`, exactement la forme de `iiif-prezi3` sur Pillow. Le motif n'était pas isolé
- [ ] Le balayage est rejoué DANS L'IMAGE : lancé sur le venv local, il ne voit pas `iiif-prezi3`, qui n'y est pas installé — le paquet qui motive ce chantier est invisible à sa propre mesure (QA-5)

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
