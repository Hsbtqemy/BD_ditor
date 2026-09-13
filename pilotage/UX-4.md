---
chantier: UX-4
statut: à venir
---

# UX-4 — cohérence visuelle inter-surfaces

**Point de départ** — l'Exploration a été soignée récemment et sert de référence ; les
QUATRE autres surfaces ne s'y sont jamais alignées. Elles étaient trois quand cette fiche
a été écrite : `/administration` est arrivée depuis (UX-10, 2026-09-07), et elle est la
plus jeune donc la moins alignée.

## Reste

### L'alignement des cinq surfaces
- [ ] Les espacements et la typographie de Recherche, Bibliothèque, Atelier et Administration suivent ceux de l'Exploration, sans valeur en dur qui contourne les tokens de `static/style.css`
- [ ] Un même composant (bouton, champ, pastille, panneau) a la même apparence sur les cinq surfaces
- [ ] **L'Administration est reprise en priorité** : ses panneaux ont été construits pour FONCTIONNER, l'un après l'autre et par des chantiers différents (INFRA-10, AUTH-3/AUTH-7, SANTE-1, EXP-1), sans qu'aucun ne réponde de l'ensemble. Attendu : les quatre panneaux se lisent comme une même page, et non comme quatre écrans empilés
- [ ] L'audit axe (`pytest -m e2e`) reste sans violation sérieuse ou critique sur les cinq surfaces et les deux thèmes après réalignement
- [ ] Aucun petit texte coloré n'utilise un accent brut : les tokens d'encre AA-sûrs sont respectés (règle d'accessibilité de CLAUDE.md)

### Le panneau des accès se lit comme un tableau
- [ ] La liste des accès d'une collection est un `<table class="corpus-table">` dans un `.table-cadre`, comme les quatre autres tableaux larges du dépôt — dont celui des comptes, sur la MÊME page : « peut exporter » et « groupe / utilisateur » s'écrivent une fois en `<th scope="col">` au lieu d'une fois par ligne
- [ ] Le `<details>` par collection RESTE, et le tableau vit dedans : c'est un dépliant, pas une ligne, et trois audits attendent `#col-body .col-item`
- [ ] La ligne d'ajout devient un `<tfoot>` dont les champs tombent sous leurs colonnes — c'est elle qui débordait de 89 px à 375 et de 144 à 320, et son `flex-wrap` de rattrapage est documenté dans `style.css` à `.contrib-add`
- [ ] `date_creation` devient une colonne « Depuis le », tronquée à dix caractères comme `derniere_vue` dans la table des comptes : `_acces_de` la renvoie déjà et l'écran n'en rendait rien
- [ ] `jamais_vu` devient une colonne « Signal », la même que la septième colonne de la table des comptes, et ses TROIS états survivent — marqueur si vrai, rien si faux, rien non plus pour un groupe, parce que l'application ne peut pas le savoir
- [ ] Les `aria-label` fabriqués par concaténation (« Niveau de X », « X peut exporter ») disparaissent au profit des en-têtes de colonne croisés avec un `<th scope="row">` portant le principal
- [ ] Les sélecteurs épinglés par les audits survivent à la restructuration **sans devenir creux** : `#col-body .col-item`, `.col-principal` (le champ de la ligne d'ajout, pas la cellule d'une ligne d'accès), `.acces-jamais-vu`, `input[data-export][data-principal]`
- [ ] `test_e2e_reflow` et l'audit axe repassent sur `/administration` : un tableau ENCADRÉ est conforme au 1.4.10, qui tolère le défilement horizontal d'un contenu à deux dimensions, mais le cadre porte `tabindex="0"` et un `role="region"` étiqueté — sans quoi la zone défilante ne s'atteint pas au clavier
- [ ] Le tableau fini ne porte **aucune colonne d'identité** — ni nom lisible, ni dernière visite, ni nombre d'actes (raison en Contexte : la réserve est écrite, et le cliquet ne la défendrait pas)
- [ ] Le `<select>` de niveau reste tel quel, et la colonne « Niveau » est faite pour pouvoir changer SEULE : la rendre en cases à cocher appartient à `AUTH-10`, sur lequel l'équipe a décidé le 2026-09-10 de ne rien engager

## Contexte

Effort M, priorité P3. Les deux cases d'accessibilité sont là parce que c'est
exactement le genre de chantier qui casse l'accessibilité sans le vouloir : réaligner des
couleurs « pour que ce soit cohérent » est la manière la plus rapide de réintroduire un
accent brut sur du petit texte, ce que le dépôt a déjà corrigé une fois.

À traiter avec UX-3, mêmes fichiers.

**L'Administration entre dans le périmètre le 2026-09-08**, sur un constat d'usage énoncé
pendant EXP-1 : *« il faudra certainement reprendre l'esthétique de cette page à l'avenir,
mais pour l'instant, on vise le fonctionnel »*. C'est un arbitrage, pas un oubli, et il
mérite d'être écrit ici plutôt que de se perdre — une intention de ce genre s'évapore
exactement comme les fiches périmées se fabriquent.

La cause est structurelle et vaut d'être notée : cette page est la seule dont les blocs
ont été posés par des chantiers SÉPARÉS, chacun ajoutant le sien sans que personne ne
réponde de l'ensemble. La version servie (INFRA-10), les collections et la vue des comptes
(AUTH-3, AUTH-7), les moteurs (SANTE-1), l'export de dépôt (EXP-1) — cinq origines, cinq
mises en forme locales. Les autres surfaces ont été dessinées d'un tenant.

## Le panneau des accès — ce qui a décidé la forme, le 2026-09-13

**D'où vient la demande.** Pendant la recette de `DROIT-2`, en regardant le panneau :
« on pourrait organiser plutôt en mode tableau et aligné ? ça permettrait de ne pas mettre
les descriptions à côté, mais au-dessus, et ne pas répéter les éléments. » C'est exactement
ce que cette fiche demande à l'Administration — se lire comme une page et non comme quatre
écrans empilés —, et le panneau des accès est le seul des quatre à ne pas déjà le faire :
la vue des comptes, dix centimètres plus bas, est un `corpus-table` à sept colonnes.

**Ce que la mise en tableau échange.** Aujourd'hui les lignes passent à la ligne
(`flex-wrap`) et restent lisibles à l'étroit, au prix d'un libellé « peut exporter »
répété autant de fois qu'il y a d'accès. Un tableau aligne au large et défile latéralement
dans son cadre à 320 px. Pour un panneau d'administration, l'alignement a été préféré —
et le défilement encadré est la voie que `tests/test_e2e_reflow.py` classe déjà conforme,
le 1.4.10 tolérant explicitement ce cas pour un contenu à deux dimensions.

**Pourquoi aucune colonne d'identité, et pourquoi ça mérite d'être écrit ici.** La
docstring de `liste_comptes` refuse déjà de joindre le nom lisible ou la dernière visite à
un propriétaire de collection : « il n'y gagnerait rien qu'il ne sache déjà (il choisit qui
il ajoute) et y verrait la composition d'équipes qui ne sont pas la sienne ». Ce panneau
est vu par des propriétaires, pas seulement par des administrateurs. **Et le cliquet des
sorties d'identité ne le dirait pas** : `/api/collections/{id}/acces` ne figure ni dans
`SORTIES_DECLAREES` ni dans `NON_BALAYE` de `tests/test_sorties_identite.py` — elle est
balayée, mais le semis n'insère aucune ligne `collection_acces`, donc la réponse est vide
et la surface passe pour muette. C'est le mode d'échec que `AUTH-5` s'écrit à elle-même.
Une colonne d'identité ajoutée ici n'allumerait donc **aucun rouge** : si le besoin revient,
elle se déclare à la main ET le semis se complète.

**Ce qui attend d'atterrir dans ce tableau**, et qui justifie de prévoir la colonne
« Signal » plutôt que de la découvrir après : deux cases ouvertes d'`AUTH-6` — une
collection dont l'unique propriétaire perd son groupe doit être signalée, et un groupe
renommé ou supprimé dans l'annuaire doit échouer en disant « je n'ai pas pu vérifier »
plutôt qu'en déclarant l'accès mort. Les deux sont bloquées sur la même décision non
prise, celle de faire lire l'annuaire à l'application — qui donnerait aussi
l'autocomplétion du champ « Login ou nom de groupe », aujourd'hui un champ libre où une
faute de frappe et un arrivant produisent la même absence.

**Repéré en chemin et laissé hors périmètre** : rien n'avertit AVANT qu'on s'apprête à
retirer le dernier propriétaire d'une collection. `_compte_proprietaires` existe côté
serveur, mais ne sert qu'à refuser en 409 une fois le geste fait. C'est un défaut
d'`AUTH-3`, pas de cohérence visuelle, et le noter ici plutôt que l'y coder est
délibéré.
