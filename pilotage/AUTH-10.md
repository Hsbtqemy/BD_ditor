---
chantier: AUTH-10
statut: à venir
---

# AUTH-10 — `ecriture` recouvre l'acte qu'on défait et celui dont on ne revient pas

**Point de départ** — 2026-09-10, en conversation, à partir d'une mesure qui cherchait
autre chose. Le `GET /api/moi` du compte `stagiaire` sur la production rend `ecriture: 0`,
et la question « faut-il un droit d'annoter ? » a rendu un constat plus précis.

**Corrigé le jour même, et la correction RENFORCE la fiche.** Ce compte-là est atypique :
des stagiaires ont bien l'écriture en production, et c'est voulu. Ce chantier n'est donc
pas ouvert sur un arrivant qui ne peut rien faire — il est ouvert sur l'inverse. **Des
personnes ont aujourd'hui le droit de supprimer un album, et aucun Ctrl+Z ne le
rattrape.** La prémisse d'origine était une lecture hâtive d'un compte d'essai ; elle est
écrite ici plutôt que remplacée, parce que c'est en la corrigeant qu'on a vu que le
risque était actuel et non hypothétique.

**`DELETE /api/albums/{id}` exige `_get_album(..., ecriture=True)` — exactement le même
droit qu'annoter une bulle.** Qui reçoit l'écriture pour annoter peut supprimer un album
entier, et `undo.py` ne connaît que quatre tables (`regions`, `annotations`,
`bulle_locuteur`, `personnage_presence`) : cette suppression-là ne se défait pas. Le seul
retour est la sauvegarde, c'est-à-dire hors de l'application.

## L'inventaire, mesuré — 73 routes mutantes

Relevé par AST sur `main.py` + `routes/*.py` le 2026-09-10. Quatre familles, séparées par
ce qui se DÉFAIT et non par l'objet qu'elles touchent.

| famille | routes | réversible ? |
|---|---|---|
| l'acte interprétatif (région) | 13 | oui, par Ctrl+Z — sauf deux |
| la structure du corpus (planche, album) | 17 | non |
| le vocabulaire (domaines, dimensions, valeurs, tags, personnages) | ~15 | non, et déborde la collection |
| la machine (lots, passes, `ml/liberer`) | ~4 | sans perte, mais accapare le `ML_LOCK` |

**Le résultat qui compte : la frontière de l'annulation passe À L'INTÉRIEUR du niveau
`ecriture`, et elle ne suit pas la hiérarchie des objets.** `PUT /api/regions/{id}/tokens/
{ordre}` et `POST /api/regions/{id}/grammaire/valider` portent le même droit et le même
objet que les onze autres routes de région, et ne sont pas annulables — la grammaire est
« dormante » pour l'undo, c'est écrit dans D1. Donc même à l'échelle d'une région,
« écriture » ne dit rien de la réversibilité.

Deux familles sont DÉJÀ séparées et ne sont pas en cause : ce qui porte sur l'instance
(`ADMIN` sur la sauvegarde et ShareDocs) et ce qui décide qui entre (`administrer`). Les
trois écarts restants sont tous à l'intérieur d'`ecriture`.

## Reste

### Trancher — et la première décision est de ne rien faire, éventuellement
- [ ] **Le REMÈDE MOINS CHER est évalué avant le remède structurel** : aligner l'undo sur son propre périmètre — rendre la correction de tokens et la validation grammaticale annulables — supprime la moitié du problème sans toucher au modèle de droits. Attendu : un chiffrage des deux, côte à côte, avant de choisir. D1 nomme déjà « grammaire/validation » comme dormante, donc le travail est identifié
- [ ] **La décision d'ajouter un niveau est prise avec son coût écrit.** Un quatrième niveau est une quatrième occasion de refus SILENCIEUX : `Portee.__init__` cumule à un seul endroit, et AUTH-3 a déjà nommé le mode d'échec — « un `in portee.ecriture` qui oublierait les propriétaires serait un refus silencieux et parfaitement crédible ». Ce défaut ne casse aucun test
- [ ] **Si un niveau est retenu, c'est `contribution`, et la raison est STRUCTURELLE et non ergonomique.** Le cumul de ce modèle est dérivé d'un ORDRE, pas stocké : `collection_acces` a pour clé primaire `(collection_id, genre, principal)` — une ligne, un seul `niveau` — et `Portee.__init__` fait `ecriture |= propriete` puis `lecture |= ecriture`. Seul ce qui s'ORDONNE peut donc s'y insérer. `lecture ⊂ contribution ⊂ ecriture ⊂ proprietaire` s'ordonne ; « vocabulaire » et « structure » ne s'ordonnent pas entre eux, et leur imposer un rang inventerait une hiérarchie que le travail n'a pas
- [ ] **Le périmètre exact de `contribution` est écrit route par route**, et il ne se déduit pas de l'objet : les 13 routes de région, corrections de tokens comprises. L'attendu est une LISTE, parce que « les routes de région » a déjà deux exceptions connues

### L'interface et le modèle sont DEUX questions, et les coller a failli coûter cher
- [ ] **L'interface se rend en CASES À COCHER, et c'est acquis quel que soit le modèle retenu.** « Écriture » ne dit à personne qu'il autorise à supprimer un album ; une case libellée « supprimer des planches et des albums » le dit. Une ÉCHELLE se rend parfaitement en cases — cocher un cran coche ceux du dessous —, donc la lisibilité s'obtient **sans toucher à `collection_acces`**. Attendu : les libellés énumèrent des ACTES, jamais des noms de niveau
- [ ] **La matrice est une décision DISTINCTE, et elle ne se prend que si une capacité résiste à l'ORDRE.** Ce qu'elle coûte, mesuré et non supposé : `collection_acces` a une ligne par personne (clé primaire `(collection_id, genre, principal)`), donc un ensemble demande une colonne-liste ou une ligne par capacité ; le cumul **cesse d'être structurel** — aujourd'hui dérivé une fois dans `Portee.__init__`, il deviendrait un test d'appartenance par question, et l'oubli qu'AUTH-3 signale se multiplierait par le nombre de cases ; enfin une matrice admet des états que le métier interdit (« peut supprimer » sans « peut lire »), donc il faudrait des règles de dépendance — c'est-à-dire une échelle réintroduite à la main
- [ ] **S'il faut une capacité hors rang, le gabarit existe DÉJÀ dans ce modèle** : `bd-admins` court-circuite entièrement `collection_acces` (AUTH-4). Une échelle et un axe orthogonal y cohabitent depuis v25. Une capacité non ordonnable serait donc **un drapeau de plus**, pas un changement de modèle — et la meilleure candidate est la curation du vocabulaire, seule des quatre familles à déborder la collection où l'on travaille
- [ ] **Le signe qu'un ordre subsiste est dans la proposition elle-même** : « toutes les cases cochées = propriétaire ». S'il existe un SOMMET, il existe un ordre au moins partiel — ce qui se demande n'est donc pas une matrice libre, mais une échelle avec une ou deux cases hors rang. L'attendu de cette case est de le vérifier plutôt que de le supposer : énumérer les paires de capacités et dire, pour chacune, si l'une implique l'autre

### Ce qui devra être vrai, si le niveau est fait
- [ ] Un compte `contribution` annote, transcrit et corrige un token, et reçoit un refus NOMMÉ sur la suppression d'une planche ou d'un album — pas un 404
- [ ] Un compte `contribution` ne peut ni fusionner deux valeurs, ni fusionner deux personnages, ni renommer un terme global : ces actes ne se défont pas et débordent la collection où l'on travaille
- [ ] Un compte `contribution` ne peut pas lancer de lot : le `ML_LOCK` est sérialisé, et le dommage n'est pas la perte mais l'ACCAPAREMENT — une passe sur tout le corpus bloque les autres pendant des minutes
- [ ] Le cliquet de `tests/test_autorisation.py` exige que chaque route ait tranché ENTRE QUATRE niveaux et non trois — sans quoi une route neuve hériterait du niveau le plus permissif par défaut et non par décision
- [ ] Le cumul est éprouvé par table de vérité aux QUATRE niveaux, et pas seulement aux extrémités : c'est le seul endroit où l'oubli d'AUTH-3 se reproduirait

### Le trou d'affichage, qui existe indépendamment de ce chantier
- [ ] **Un refus d'écriture sur une donnée est un 404, et il ment à qui VOIT l'objet.** `_get_region(..., ecriture=True)` lève « Région 42 introuvable » sur une région affichée à l'écran. La règle vient d'AUTH-2 — « 404, jamais 403 : "existe mais pas pour vous" révèle la composition du corpus » — mais elle ne s'applique PAS ici : la personne lit déjà cette région. Le 404 ne lui cache rien du corpus, il lui cache la raison du refus. Attendu : un 403 nommé quand l'objet est LISIBLE et l'écriture refusée, le 404 restant pour qui ne le voit pas. La doctrine n'est pas rompue, elle est précisée
- [ ] Ce raffinement est éprouvé dans les DEUX sens — un lecteur reçoit 403 sur ce qu'il voit, un étranger reçoit 404 sur ce qu'il ne voit pas — sans quoi on aurait remplacé un mensonge par une fuite

## Contexte

**Pourquoi ça se pose maintenant et pas avant.** Le modèle à trois niveaux répond à
*« jusqu'où t'a-t-on laissé entrer »* : c'est un axe d'APPARTENANCE, et il était juste tant
qu'une collection était l'espace d'une équipe qui se connaît. « Peut annoter » est un axe
d'ACTE. Les mélanger est ce qui pourrit un modèle de droits, donc l'absence n'était pas un
oubli — c'était une frontière tenue. Ce qui change, c'est l'arrivée de gens dont le métier
est exactement UNE des familles.

**Ce que le chantier ne doit pas devenir.** Un modèle de capacités où chaque acte a son
drapeau. Le cumul de ce modèle est dérivé d'un ordre ; passer à un ENSEMBLE demanderait de
renoncer à la clé primaire de `collection_acces` ou d'y stocker une liste, et de rendre
EXPLICITE un cumul aujourd'hui structurel. C'est précisément là que naissent les refus
silencieux.

**Voisinage.** `AUTH-2` (le point de passage unique, et le 404 qui ne fuit rien), `AUTH-3`
(les trois niveaux et le piège du cumul), `D1` (l'annulation, son périmètre et ses
dormances), `AUTH-6` (le modèle de comptes, qui a soulevé la question par un
`ecriture: 0`), `COL-2` (les descripteurs, l'autre chose qu'on ne peut pas encore régler à
l'écran).
