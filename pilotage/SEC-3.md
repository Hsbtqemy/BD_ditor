---
chantier: SEC-3
statut: à venir
---

# SEC-3 — une dépendance nous retient sous un correctif de sécurité

**Point de départ** — trouvé le 2026-09-07 par la passe de revue de QA-4, en posant la
question « qu'est-ce que ce correctif a OUVERT ? » à une descente de version. Aucun test
ne pouvait le voir : les suites vérifient qu'on n'a rien cassé, jamais qu'on n'a rien
laissé ouvert.

## Reste

### Fermer le vecteur, indépendamment des versions
- [ ] Les quatre `Image.open()` du dépôt (`pipeline/ingest.py` l. 60 et 88, `pipeline/ocr.py` l. 71 et 74) passent `formats=[…]` restreint à ce que le corpus contient réellement — c'est le contournement officiel de l'avis, et il vaut quelle que soit la version de Pillow installée
- [ ] Un PSD forgé déposé dans `corpus/` est REFUSÉ à l'ingest, et un test le prouve plutôt que la lecture du code
- [ ] La liste des formats est tirée d'un seul endroit : quatre listes recopiées divergeraient, et c'est le format NON couvert qui rouvrirait le trou

### Trancher le plafond
- [ ] Le choix est arrêté et écrit : garder `Pillow<=12.0.0` et rester sous le correctif ; monter Pillow et perdre la validation IIIF stricte ; ou isoler `iiif-prezi3` dans son propre environnement pour avoir les deux
- [ ] Si l'on garde le plafond, la condition de RÉOUVERTURE est écrite avec lui — sur le patron de la sauvegarde de DROIT-1, dont la condition s'est déclenchée dès le lendemain

### Chercher la forme, pas l'endroit
- [ ] La question est posée UNE fois pour tout le verrou : quel autre paquet épinglé porte un plafond qui retient un correctif de sécurité ? Le constat ci-dessus décrit un endroit ; rien ne dit que `pillow` soit le seul

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
négatives, et la croire suffisante serait l'erreur. Rien dans le dépôt ne restreint les
formats aujourd'hui : `Image.open(source)` accepte tout ce que Pillow sait lire, alors que
le corpus n'est que du TIFF master et du JPEG dérivé.

**Pourquoi une fiche plutôt qu'un commit dans QA-4.** Le contournement seul tiendrait en
un commit, et la règle serait alors de ne pas ouvrir de fiche. Mais il ne referme pas le
sujet : le plafond, sa condition de réouverture et le balayage des autres paquets sont un
arbitrage, pas une correction. QA-4 est par ailleurs un chantier de DÉPENDANCES — y
glisser une modification de `pipeline/` ferait mentir son périmètre.
