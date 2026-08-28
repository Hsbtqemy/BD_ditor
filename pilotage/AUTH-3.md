---
chantier: AUTH-3
statut: différé
---

# AUTH-3 — espaces de travail : ouvrir une collection, y être invité

**Point de départ** — mis en attente derrière AUTH-2 : sans point de passage unique, une
invitation ne garantit rien. Le conteneur, lui, existe déjà depuis la v14.

## Reste

### Propriété
- [ ] Une collection a un propriétaire, distinct de son champ descriptif `responsables` (JSON bibliographique nom/rôle/orcid, qui reste ce qu'il est : de la métadonnée de dépôt, pas un droit d'accès)
- [ ] Un utilisateur crée une collection depuis l'UI et en devient propriétaire — aujourd'hui `tools/gerer_collections.py` est le SEUL outil d'écriture, et il exige un accès shell
- [ ] Un propriétaire accorde et retire un accès à un autre utilisateur ou à un groupe, avec un niveau (lecture, écriture)
- [ ] La table qui porte ces accès EXISTE depuis AUTH-2 (`collection_acces` : collection × principal × niveau, `principal` = un login ou un nom de groupe). Ce chantier n'a donc plus à l'inventer : il lui faut une route d'écriture, une notion de propriétaire, et un écran

- [ ] Un album se DÉPLACE d'une collection à l'autre depuis l'UI : AUTH-2 fait choisir la collection à la création, mais le champ disparaît à l'édition, faute de propriétaire pour dire qui a le droit de déplacer quoi

### Ce qui doit rester vrai
- [ ] Retirer un accès ne détruit aucune donnée : les annotations faites par la personne restent, et le journal A3 continue de les lui attribuer
- [ ] Supprimer une collection ne supprime pas ses albums (aujourd'hui `collection_album` est une appartenance N-N ; le lien se défait, l'album survit)
- [ ] Une collection sans aucun accès accordé reste accessible à son propriétaire — pas de collection orpheline et inatteignable
- [ ] Le mono-poste local sans auth voit tout, comme aujourd'hui

## Contexte

**Reçu d'AUTH-2 le 2026-08-28.** Le cloisonnement est fait : `autorisation.py` tranche
« qui voit quoi », 99 routes sur 111 le consultent, et `collection_acces` est peuplée — mais
uniquement en SQL à la main. AUTH-2 avait dupliqué deux cases qui vivaient déjà ici (créer
une collection depuis l'UI, accorder un accès) ; elles lui ont été retirées, parce que la
version d'ici vient avec le PROPRIÉTAIRE, sans lequel « qui a le droit de partager » n'a
pas de réponse. Ce chantier est donc devenu le seul obstacle entre le cloisonnement et son
usage réel.

**C'est le modèle demandé le 2026-08-27 : « qu'un utilisateur puisse ouvrir une nouvelle
base, être ajouté à une qui existe ».** Le mot « base » y désigne un espace de travail,
pas un fichier SQLite — et c'est ce qui rend le chantier abordable.

Le conteneur est déjà là. `collection` (v14) porte `nom`, `description`, `licence_defaut`,
`base_legale`, `statut_diffusion`, `date_embargo`, `responsables`, une période de
couverture, et une appartenance N-N aux albums. Elle a été bâtie comme unité de DÉPÔT ;
c'est un espace de travail qui s'ignore. Il ne manque que la propriété et les accès.

**Un fichier SQLite par espace a été écarté** (arbitrage du 2026-08-27) : `BD_DB_PATH` est
certes configurable, mais toute l'application suppose une base unique via `Depends(db)`
(93 points), et l'isolation dure coûterait l'analyse inter-corpus — or l'Exploration,
l'accord inter-annotateurs et la recherche FTS n'ont d'intérêt que sur un corpus réuni.
Le cloisonnement est donc logique, pas physique, et sa solidité repose entièrement sur
AUTH-2. C'est le compromis à assumer les yeux ouverts : un bug d'ACL expose, là où des
fichiers séparés auraient protégé.
