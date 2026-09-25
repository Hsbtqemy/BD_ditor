# Lexique situé — vocabulaire SKOS documenté (A4)

> **But.** Rendre le vocabulaire ÉMERGENT du corpus (attributs facettés **et** tags)
> non seulement contrôlé mais **documenté et situé** : chaque terme peut porter une
> **définition**, une **note de portée** (« ici, ce mot signifie X »), un **état** de maturité
> et une **portée d'appartenance** (global ou propre à une collection). C'est la brique FAIR
> *Interoperable/Reusable* : un tiers sait exactement ce que chaque terme voulait dire dans
> l'étude. Décision arrêtée le 2026-07-15, livrée en **v17**. Cadre : niveau 7 du
> `docs/dictionnaire-metadonnees.md`.

## SKOS, appliqué à notre vocabulaire

**SKOS** (W3C) décrit un vocabulaire contrôlé : des *concepts* dans des *schémas*, avec
libellé, définition, note de portée, et liens. Correspondance :

| Notre schéma | SKOS | Rôle |
|---|---|---|
| `attribut_dimension` (axe, ex. « registre ») | schéma / facette | le référentiel |
| `attribut_valeur` (ex. « argot ») | `skos:Concept` (`inScheme` sa dimension) | le terme |
| `valeur` / `label` | `skos:prefLabel` | libellé préféré |
| **`definition`** | `skos:definition` | le sens |
| **`note_portee`** | `skos:scopeNote` | **le cadre d'emploi = le « situé »** |
| **`etat`** `provisoire → defini` | *(statut projet, miroir `auto→validé`)* | maturité |
| **`collection_id`** | portée d'appartenance (≈ `inScheme` d'une étude) | global / local |
| *(A5, dormant)* alignement | `skos:exactMatch` | lien Wikidata / IdRef |

**Un seul patron, appliqué partout.** La même couche définitionnelle est posée sur les
**dimensions**, les **valeurs** ET les **tags** — les trois vocabulaires « contrôlés-mais-
ouverts » du projet. Pour un **tag**, la `description` (déjà là) **EST** la `skos:definition` ;
il gagne en plus `note_portee`, `etat`, `collection_id`. (Les rôles de contribution restent
hors périmètre : leur « définition » est le relator MARC.)

## Portée d'appartenance — patron *mentions→entités*

`collection_id` **NULL = global** ; renseigné = **local** à une collection (un terme forgé pour
une étude). La **promotion local→global** = repasser à NULL. Corollaire de sûreté : supprimer
une collection **PROMEUT** ses termes locaux en global (`ON DELETE SET NULL`) plutôt que de
perdre le vocabulaire. C'est le même mouvement que personnages / contributeurs (mention locale
→ entité canonique), cf. `docs/personnages-et-attribution.md`.

### Un terme n'est jamais plus global que son parent (v24)

Le vocabulaire est HIÉRARCHIQUE — domaine → dimension → valeur — et sa portée descend avec
lui : une dimension **hérite** de la portée de son domaine, une valeur de celle de sa
dimension. Une valeur globale sous un axe local serait un état sans signification, et
AUTH-2 en fait un problème concret : les routes à plat (`GET /api/attributs/valeurs`,
attributs d'un objet) renvoient le **nom de la dimension** avec chaque valeur. Ce qui
échappe alors n'est pas le mot mais l'axe d'analyse — une grille, pas un terme.

Trois couches, parce qu'une seule ne suffisait pas :

1. **à la création**, le terme prend la portée de son parent (les routes n'avaient jamais
   posé de `collection_id`, d'où le défaut) ;
2. **à la lecture**, le terme PARENT est filtré en plus du terme — l'héritage ne vaut que
   pour l'avenir, or toute base antérieure porte déjà des lignes incohérentes ;
3. **en migration** (v24), la portée redescend une fois pour toutes. Sans cette étape, le
   « % défini » ci-dessous continuerait de compter un terme que les listes masquent, la
   portée étant comptée par appartenance.

L'inverse — un terme **local sous un parent global** — reste parfaitement légitime : une
étude peut ajouter sa valeur à un axe partagé.

**Rattacher ne déplace pas** (renversement daté du 2026-09-24, AUTH-11). v24 faisait suivre
la portée d'une dimension RATTACHÉE à un domaine : globale sous un domaine privé, elle y
descendait avec ses valeurs globales — et disparaissait sans un mot des autres collections ;
locale sous un domaine global, elle devenait globale — et son nom se publiait. Deux
déplacements que personne n'avait demandés. Désormais `PATCH …/domaine` ne touche que le
`domaine_id` : permis sous un domaine global ou de la même collection, **409** sous un domaine
propre à une autre collection que celle de la dimension (dimension globale comprise), avec la
marche à suivre — ranger d'abord la dimension (`PATCH …/lexique`, qui, lui, fait descendre la
portée : la dimension, et ses valeurs globales avec elle ; depuis le 2026-09-25, l'écran
recharge le lexique après chaque rangement, et la descente se voit), sans promettre que ce
rangement réussira. L'import de vocabulaire refuse les mêmes lignes.

**Ranger ne sépare pas un terme de ses termes liés** (décidé le 2026-09-25, AUTH-11). Le
rangement (`PATCH …/lexique {collection_id: C}`) était la troisième porte vers un terme rangé
hors de la collection de son parent : une dimension sous un domaine de A rangée dans B, ou
rangée dans B en laissant en A une valeur locale. Il est refusé désormais, par un **409** qui
dit pourquoi, si le **parent** du terme est local à une autre collection que C, ou si un terme
**qui en dépend** l'est — y compris sous un enfant global que la descente emmènerait. Un parent
global convient ; les enfants globaux descendent comme avant ; ceux déjà dans C ne bougent
pas ; un tag n'a ni parent ni enfant. Un **renvoi** — ranger un terme dans la collection où
il est déjà — ne juge pas ses enfants directs, que rien ne déplace (sans quoi une base
antérieure ne s'éditerait plus), mais juge ce que la descente déplacerait : sous un enfant
global, un terme d'une autre collection refuse le renvoi, plutôt que de laisser descendre
l'enfant au-dessus de lui (choix daté du 2026-09-25, après relecture : ne plus faire
descendre aurait laissé l'enfant global au-dessus d'un parent local, l'état que v24
répare). Le refus nomme les termes liés que l'appelant lit ; ceux qu'il ne lit pas deviennent
« un terme lié que vous ne lisez pas », une seule fois. La promotion vers Global garde ses
propres règles (ci-dessus).

**Ranger la racine emporte sa branche** (option β, tranchée par Hugo le 2026-09-25). Au premier
jet de la règle ci-dessus, une branche entièrement locale à A ne passait plus à B que par
Global : chaque pas séparait un terme de son voisin, et il fallait la promouvoir
(`promouvoir_parents`) puis ranger sa racine — la branche publique entre les deux gestes.
Désormais, ranger de A vers B un terme **sans parent local** (un domaine, une dimension sans
domaine ou sous un domaine global, une valeur sous une dimension globale) déplace aussi, d'un
seul geste, ses descendants rangés dans A ; les descendants globaux descendent comme avant.
Restent refusés un descendant d'une **troisième** collection et le **milieu** d'une branche
(son parent est ailleurs, ou déjà dans B : ce n'est pas une racine). Depuis Global, rien n'est
emporté — privatiser un terme global est une autre question (`COL-1`). Emporter, c'est
écrire : les emportés sont dans A, où il faut déjà écrire pour ranger la racine. La réponse
les nomme dans `promus`, et l'écran recharge le lexique : leurs éditeurs disent leur
nouvelle portée.

## Édition — l'API et l'UI

- **API** (partielle, un `PATCH` par champ) :
  `PATCH /api/attributs/dimensions/{id}/lexique`, `.../valeurs/{id}/lexique`,
  `PATCH /api/tags/{id}/lexique` — corps `{definition?, note_portee?, etat?, collection_id?}`
  (`collection_id: null` explicite = promotion en global). `GET /api/lexique` renvoie tout le
  lexique (dimensions → valeurs + tags) + le résumé **% défini** ; `GET /api/collections`
  alimente le menu de portée.
- **UI** : bouton **📖 Lexique** sur la page Exploration → modale accessible (module
  `dialog.js` : piège à focus, Échap, retour du focus). Chaque terme est un `<details>`
  éditable (définition, note de portée, case « Défini », menu Portée) ; un compteur **% défini**
  suit la maturité en direct. Audit axe (WCAG 2.1 AA) verrouillé (`pytest -m e2e`).

## Indicateur « % défini »

`database.lexique_resume(conn, collection_id)` — part des termes (dimensions + valeurs + tags)
à l'état `defini`, **scopée par appartenance** (global ⊕ local à la collection). Nourrit la
qualité de la Collection ; exposé dans les exports sous `paradonnee.lexique`
(`metadonnees_collection.py`) et `vocabulaire.lexique` (`description_collection.py`).

Servi par `GET /api/lexique`, il se filtre **comme les quatre listes de la route** : sans
cela le panneau annonçait « 3 définis sur 41 » à qui n'en voit que trois — le total disant
le volume de vocabulaire des autres, et le pourcentage devenant faux pour qui le lit. La
fonction reçoit alors un **fragment SQL de portée** (`clause=`) plutôt qu'une `Portee` :
`database.py` n'a pas à dépendre de `autorisation.py`, et la règle reste écrite au seul
endroit qui la porte.

## Export

Les records portent la couche SKOS : chaque dimension/valeur du bloc `vocabulaire` et chaque
`tags` gagnent `definition` / `note_portee` / `etat` / `collection_id` (JSON arbre + tables CSV
`vocabulaire`/`tags`). Le `% défini` remonte dans la paradonnée et le roll-up. Cf.
`docs/export-metadonnees.md`.

## Périmètre & suites

- **Livré (v17)** : schéma (4 colonnes × dimensions/valeurs, 3 × tags) + API + UI + indicateur
  + export. Tests : `tests/test_lexique_situe.py` (+ e2e/axe dans `tests/test_e2e_a11y.py`).
- **Dormants (déclenchables plus tard)** : **définition contextuelle** `valeur_definition`
  (glose d'un terme *par collection*, si un terme diverge vraiment entre études) ; **version**
  de concept (le gel se fait au niveau Collection) ; **alignement d'autorité** (A5,
  `skos:exactMatch` → Wikidata/VIAF/IdRef) ; unification mécanique des quatre vocabulaires
  (tags / attributs / rôles / lexique) en un seul patron (refonte, pas maintenant).
