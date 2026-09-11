---
chantier: AUTH-11
statut: à venir
---

# AUTH-11 — un terme qu'on ne lit pas ne se montre pas, ne sort pas, ne se devine pas

**Point de départ** — 2026-09-11, détaché de `DROIT-2` le jour même. La session d'ANA-6
avait mesuré que `_recherche_rows` montrait un tag local à une collection que le lecteur ne
lit pas ; l'équipe l'a confié à DROIT-2, en tête. La moitié « tags » s'y est fermée en deux
commits : les lectures qui ont leur propre requête (`df20d3d`), puis l'Atelier et les
exports d'un album, où l'écriture PRÉSERVE ce qu'elle cache (`a2ed353`). La passe de revue a
trouvé les six cases ci-dessous, et elles ne portent pas sur le droit d'exporter : elles
portent sur ce qu'on VOIT d'un terme. Laissées dans DROIT-2, elles auraient tenu ouvert un
chantier livré ; elles ont déménagé ici telles quelles, sauf la queue de la première, qui
avait vieilli dans la journée.

**La règle est déjà écrite, et ce chantier ne la change pas** : un tag, un domaine, une
dimension ou une valeur se voit s'il est GLOBAL ou local à une collection qu'on lit
(`portee.clause_terme`, AUTH-2 ; CLAUDE.md, § Autorisation par collection). Ce qui reste,
ce sont des lectures qui ne la consultent pas — et trois d'entre elles ne MONTRENT rien :
ce sont des oracles, où le terme se devine à la réponse.

## Reste

### Ce qui sort de l'instance
- [ ] **Les exports de dépôt d'une collection emportent les termes des AUTRES collections** — le catalogue de tous les tags de l'instance avec leur définition et leur `collection_id` (`metadonnees_collection`, clé `tags_cat` : JSON et onglet « tags ») ; les tags posés, sans portée des termes (`ann_tags`) ; les valeurs d'attribut des personnages (`perso_attr`) ; les sujets DataCite et Dublin Core, qui prennent tous les tags et toutes les valeurs (`crosswalk_depot._sujets`). Ces artefacts QUITTENT l'instance. Attendu : l'export de A ne porte que le vocabulaire de A — global ⊕ local à A, la règle que suit déjà le « % défini » —, quel que soit qui exporte ; et `docs/export-metadonnees.md`, qui dit « les catalogues de référence restent globaux », réécrit avec. **Reporté le 2026-09-11 par l'équipe, « avec les portes, plus tard »** — et les portes ont reçu leur garde le même jour sans lui (`4b1d530`) : le report n'attend donc plus rien qui le rouvrira de lui-même. C'est le premier dépôt qui le rend pressant, et le renvoi est posé dans `DEPOT-1`

### Ce qui se montre
- [ ] **L'axe « dimension » du croisement lit une dimension par son identifiant, sans portée** — `dim:<id>` d'une collection qu'on ne lit pas rend son NOM (le libellé de l'axe) et ses valeurs. Attendu : un 404, comme pour un terme absent, et une valeur illisible ne fait pas de ligne (la portée posée sur la liaison, comme sur l'axe des tags). **Reporté le 2026-09-11 par l'équipe**
- [ ] **Une région dont il ne reste que des tags cachés reste marquée « annotée »** — `annotee`, `nb_annotees` et le compteur de la Recherche lisent l'existence de la ligne `annotations` : l'écran montre une région annotée sans rien d'annoté. Un indice mineur. Attendu : le marqueur suit ce qu'on voit, ou la limite est écrite

### Ce qui se devine sans se montrer
- [ ] **Le filtre par valeur d'attribut (`attributs=<id>`) ne vérifie que l'EXISTENCE de la valeur** (`_valider_facette`) — un oracle par énumération d'identifiants, sans nom. Attendu : la même règle que le filtre par tag
- [ ] **L'index plein texte contient le nom des tags** : une recherche par mot trouve une région par un tag qu'on ne lit pas, sans l'afficher. Un oracle — il faut connaître le mot. Attendu : décider si l'index garde les tags, l'oracle étant alors écrit comme une limite, ou s'il les perd au profit du seul filtre par tag
- [ ] **Taper le nom d'un tag caché l'attache** : le libellé est unique dans toute l'instance (`_ensure_tags`, `ON CONFLICT(label)`), donc qui tape le nom d'un tag local à une collection qu'il ne lit pas s'attache CE tag — qui disparaît aussitôt de son écran. Un oracle par l'écriture. Attendu : il se ferme par une unicité (libellé, collection), c'est-à-dire un changement de schéma, pas par une garde

## Contexte

**Pourquoi un chantier et pas six commits.** Les six n'ont pas le même remède. Deux sont
une clause de portée à poser (l'axe dimension, le filtre par valeur). Une est la réécriture
d'un export et de sa documentation (le dépôt). Une est une DÉCISION : garder l'oracle de
l'index plein texte en l'écrivant comme limite, ou retirer les tags de l'index. Une est un
changement de SCHÉMA (l'unicité du libellé). La dernière est un indice mineur, qui peut
aussi s'écrire comme limite. Ce qui les réunit est la question qu'elles posent, pas le code
qu'elles touchent.

**Le patron à suivre existe, en deux moitiés.** Pour LIRE, l'axe « tag » du croisement
(`df20d3d`) : la portée se pose sur la LIAISON et pas seulement sur le terme nommé, sans
quoi un axe lisible compterait des valeurs illisibles. Pour ÉCRIRE, l'annotation
(`a2ed353`) : une route qui réécrit ce qu'elle voit doit remettre ce qu'elle cache
(`_tags_caches`), sinon enregistrer efface le travail d'une autre collection — et le
journal doit garder la ligne ENTIÈRE, sans quoi Ctrl+Z l'efface à son tour. Toute
fermeture sur les dimensions et les valeurs devra se poser la même question avant d'écrire
la clause : les attributs d'une région ou d'un personnage se réécrivent-ils en bloc ?

**L'unicité du libellé croise COL-1.** Fermer la collision par une unicité (libellé,
collection) permet deux tags « X », l'un global, l'autre local. Promouvoir le local en
global — le geste central de COL-1 — rencontre alors son homonyme, et il faudra choisir :
fusionner, refuser, renommer. Aujourd'hui la question ne se pose pas parce que le libellé
est unique partout ; c'est exactement ce qui fait l'oracle. Renvoi posé dans COL-1.

**Voisinage.** `DROIT-2` (d'où ces cases viennent, et les deux commits qui ont fermé la
moitié « tags »), `AUTH-2` (la règle `clause_terme`), `COL-1` (la promotion des termes, et
l'unicité), `DEPOT-1` (le premier dépôt, qui rend pressante la case des exports), `ANN-1`
(le vocabulaire d'étude : s'il naît LOCAL, l'axe dimension du croisement cesse d'être une
hypothèse).
