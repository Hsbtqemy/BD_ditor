---
chantier: COL-2
statut: à venir
---

# COL-2 — gérer une collection à l'écran, et pas seulement en ligne de commande

**Point de départ** — 2026-09-10, trouvé pendant la passe de QA d'EXP-1. Une case demandait
une collection déclarée `public` ; l'écran d'Administration **AFFICHE** `statut_diffusion`
(« sans régime ») et ne permet pas de le changer. Il a fallu un troisième terminal et
`tools/gerer_collections.py modifier 1 --statut public`. Décidé dans la foulée : il faut une
interface, **probablement dans la Bibliothèque**.

**Le chantier est plus petit qu'il n'en a l'air, et c'est le fait à retenir avant de
l'ouvrir.** `PATCH /api/collections/{id}` existe, il est **gardé** (`_get_collection(...,
administrer=True)`, donc propriétaire), il valide le vocabulaire contrôlé de
`statut_diffusion` (422 nommant les valeurs admises) et il protège le nom réservé de la
collection de repli. Dix champs sont déjà acceptés par `CollectionUpdate` : `nom`,
`description`, `licence_defaut`, `base_legale`, `statut_diffusion`, `date_embargo`,
`date_debut`, `date_fin`, `referent_nom`, `referent_contact`. **Il n'y a rien à écrire côté
serveur** — c'est un chantier de front.

## Reste

### Trancher, avant d'écrire une ligne
- [x] **Où vit l'écran, et la raison est écrite — tranché le 2026-09-10 : la BIBLIOTHÈQUE.** La frontière, qui est l'attendu de cette case et non la préférence : **_qui entre_ relève de l'INSTANCE et vit dans Administration ; _ce que la collection EST_ relève du CORPUS et vit dans la Bibliothèque.** Le panneau **👥 Collections** (AUTH-3) garde donc les accès, et les dix champs de `CollectionUpdate` — régime de diffusion compris — vont à la Bibliothèque. La phrase se vérifie sur le cas limite qui la teste le mieux : `statut_diffusion` décide de ce qui SORT, ce qui sonne administratif, mais il décrit ce que la collection EST vis-à-vis du dehors et se lit à côté de sa licence et de son embargo — pas à côté de la liste de ses membres. Cohérent avec UX-10, dont Administration porte « ce qui porte sur l'INSTANCE et non sur un album »
- [ ] **Quels champs entrent dans le formulaire, et lesquels restent dehors.** Les dix de `CollectionUpdate` ne sont pas de même nature : descripteurs (`nom`, `description`, `date_debut`/`date_fin`), droits (`licence_defaut`, `base_legale`, `statut_diffusion`, `date_embargo`), exploitation (`referent_nom`, `referent_contact`). Un formulaire plat les mettrait sur le même plan alors qu'ils n'engagent pas la même chose
- [ ] **La garde de l'écran est celle de l'ACTE, et elle est nommée.** Le serveur exige `peut_administrer` — propriétaire, pas simple écriture —, et c'est justifié : ces champs décident de ce qui SORT de l'instance (DROIT-1). L'écran doit poser sa propre question plutôt que d'hériter de celle de son contenant : c'est la leçon d'AUTH-4, où le référent, une simple adresse, s'est retrouvé derrière la garde du PARTAGE
- [ ] **Le sort de `tools/gerer_collections.py` est décidé et écrit.** Il ne disparaît pas — c'est ainsi qu'un script agit —, donc deux portes mènent au même champ. `statut_diffusion` a déjà vécu cet état : l'outil validait, la route non, et « un champ à deux portes dont une seule contrôle n'est pas contrôlé ». La validation est partagée depuis (`config.STATUTS_DIFFUSION`) ; toute règle ajoutée par l'écran devra l'être au même endroit

### Les trois pièges du formulaire, qui ne se devinent pas
- [ ] **`date_embargo` RETIENT, elle ne PROMEUT jamais.** Une échéance passée ne rend rien publiable toute seule, et une date ILLISIBLE retient aussi. Un champ de date qui suggérerait le contraire ferait passer une faute de frappe pour une décision. L'écran doit dire ce que la date fait, pas seulement l'accepter
- [ ] **`referent_*` et `responsables` ne sont pas la même chose, et un formulaire les confondrait.** Le référent est une ADRESSE d'exploitation qui ne sort d'AUCUN artefact (un test le vérifie) ; les responsables sont scientifiques, portent un ORCID et partent au dépôt. Les afficher côte à côte sans les distinguer défait ce qu'AUTH-4 a payé
- [ ] **Le nom de la collection de repli est RÉSERVÉ**, et la garde interdit de le PRENDRE, pas de le conserver. Un formulaire qui refuserait d'enregistrer la collection de repli sans la renommer la rendrait inéditable — le serveur le sait déjà, l'écran doit rendre son 422 lisible plutôt que le reproduire

### Ce qui doit se voir à l'écran une fois fait
- [ ] Depuis la surface retenue, un propriétaire pose `statut_diffusion` à `public` sans ouvrir de terminal, et le manifeste IIIF de cette collection cesse d'emporter son `AVERTISSEMENTS.txt` — c'est le geste exact qui a manqué le 2026-09-10
- [ ] Une valeur hors vocabulaire est refusée avec la liste des valeurs admises, et non par un champ libre qui accepte tout puis échoue au dépôt
- [ ] L'échéance d'embargo dépassée est SIGNALÉE là où on la modifie, comme elle l'est déjà sur l'écran Collections et dans le manifeste : sans quoi un corpus reste fermé par inertie
- [ ] Une personne en écriture seule ne voit pas le formulaire, et une personne sans accès ne voit pas la collection — les deux refus sont distincts et aucun ne révèle l'existence de ce qu'il cache

## Contexte

**Ce que l'écart coûte aujourd'hui.** Le régime de diffusion décide de ce qui quitte
l'instance (DROIT-1) : il est ce que le manifeste DÉCLARE, et ce qui retient ou libère les
images au dépôt. Il est affiché sur un écran d'administration et modifiable nulle part
ailleurs qu'en ligne de commande, sur une machine qui a le dépôt et la base sous la main.
Un administrateur qui le LIT essaiera de le changer — c'est ce qui s'est produit le
2026-09-10, en pleine passe de QA.

**Pourquoi ce n'est pas un simple oubli.** La ligne de commande était le bon outil tant que
les collections se créaient au montage d'un corpus, par la personne qui l'hébergeait. Depuis
AUTH-3, une collection est un espace de travail qu'on ouvre pour une étude, et depuis
AUTH-7 les comptes se gèrent sans SSH. L'écrit est resté en arrière du modèle.

**Voisinage.** `AUTH-3` (le panneau des accès, déjà dans Administration), `AUTH-4` (le
référent, et la garde d'écran qui se pose sur l'acte), `DROIT-1` (ce que le régime borde, et
ce qu'il ne borde pas), `EXP-1` (l'export de dépôt, dont la QA a révélé le manque),
`UX-10` (l'administration rassemblée), `COL-1` (l'incubateur, qui fera circuler le travail
ENTRE collections et supposera qu'on sache les décrire).
