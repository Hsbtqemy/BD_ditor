# Annulation (undo) — D1

> **But.** Rendre RÉVERSIBLE le geste d'annotation le plus dangereux — la **suppression
> cascade** (une case emporte ses bulles + annotations + tags), aujourd'hui irréversible sans
> restaurer une sauvegarde complète. Filet **fin**, complément de la sauvegarde (« gros grain »).
> Débloqué par le journal A3 (v16). Cadre : backlog **UX-5**.

## Le journal EST l'historique

Pas de pile client, pas de nouvelle table : le journal `evenement` (A3) porte déjà tout ce
qu'il faut — append-only, état **`avant`/`apres`**, **instantané profond** capturé à la
suppression, et un `cible_id` qui **survit** à la destruction de sa cible (pas une FK). Annuler,
c'est **remonter** ce journal en appliquant l'inverse de chaque acte.

## Pile via événements d'annulation (append-only préservé)

Un événement n'est **jamais** modifié. Annuler un acte `E` = exécuter son inverse **+ ajouter**
un événement `annulation` (`cible_table='evenement'`, `cible_id = E.id`). La **dernière action
annulable** est l'événement **humain** le plus récent, d'un type annulable, **non déjà
référencé** par une annulation. `Ctrl+Z` répété remonte ainsi l'historique — une **pile**, sans
état mutable. (Le **redo** — annuler une annulation — est hors périmètre de ce cran.)

## Inversions (`undo.py`)

Mutations **brutes** + réindex FTS, **sans repasser par les routes** (sinon elles
rejournaliseraient → bruit + boucle). Un **seul** événement `annulation` est ajouté par undo.
L'ensemble (inverse + journal) est **atomique** : la route commite, la dépendance `db` fait
rollback en cas d'échec.

| Acte journalisé | Inverse |
|---|---|
| `creation` région | supprimer la région (+ sous-arbre, désindexé) — **refusé** si quelqu'un d'autre l'a modifiée, annotée, y a rattaché une région, ou lui a donné un locuteur, un personnage montré ou une situation depuis (CONC-4) |
| `modification` région (géométrie / OCR / déplacement) | remettre les colonnes que l'acte a CHANGÉES à leur valeur `avant` — **refusé** si l'une d'elles a changé depuis (sauf par un moteur) |
| `modification` région qui a changé le type d'une zone de texte en case ou en boîte personnage | remettre le type, puis **reposer le locuteur** que le changement avait retiré (ANN-8), s'il est rendable — sinon le type revient seul, et la réponse le compte (`liens_non_rendus`) ; **refusé** (409 nommé) si la région porte aujourd'hui un AUTRE locuteur |
| `modification` région qui a changé le type d'une boîte personnage ou d'une case | le miroir : remettre le type, puis **reposer le personnage montré ou la situation** que le changement avait retirés — **refusé** (409 nommé) si la boîte montre aujourd'hui un AUTRE personnage ; la situation revient par différence, à côté de celle qu'un autre a posée |
| `modification` région qui rend un type sans locuteur (case, boîte personnage) | comme toute modification — **refusé** (409 nommé) si la région porte aujourd'hui un locuteur AUTRE que celui que l'acte avait laissé (sa photographie, `liens_vus`) |
| `suppression` région | **recréer le sous-arbre** depuis l'instantané profond (région + annotation + enfants, **mêmes `id`**) — **passé** si un `id` a été repris, si une planche ou le parent n'est plus le même, ou si l'on n'écrit plus dans l'une des planches |
| `creation` / `modification` / `suppression` annotation | défaire ce que l'acte a CHANGÉ, sur l'état actuel : la note revient à `avant` si l'acte l'a changée ; les tags qu'il a ajoutés partent, ceux qu'il a retirés reviennent ; vide, l'annotation est supprimée |
| `lien` locuteur/présence (avant ∅) | retirer le lien — **refusé** (409 nommé, champ `locuteur` ou `presence`) si la région porte aujourd'hui un AUTRE personnage que celui que l'acte avait posé (ANN-8) |
| `lien` (avant présent) / `delien` | rétablir l'ancien lien — **passé** si la région n'est plus d'un type qui le montre : un locuteur hors d'une zone de texte, un personnage montré hors d'une boîte personnage (ANN-8) ; sinon **refusé** (409 nommé) si elle porte aujourd'hui autre chose que ce que l'acte avait laissé (son personnage, ou aucun pour un `delien`) et que l'ancien lien |

**Un locuteur part avec le type, et revient avec lui** (ANN-8, tranché par Hugo le
2026-10-21). Une bulle, un cartouche ou une zone de texte qui devient case ou boîte
personnage perd son locuteur : il restait, invisible à l'écran, et comptait encore au
registre, dans la Recherche et les exports. Le retrait entre dans l'acte du changement de
type — son `avant` porte `locuteur`, la clé d'un nœud d'instantané profond —, et non dans un
`delien` à part : UN Ctrl+Z rend le type ET le locuteur. Deux actes en auraient demandé deux,
et le premier aurait rendu une bulle muette que personne n'a voulue. Le locuteur revient par
la même porte que les liens d'une suppression, sous les mêmes questions : le personnage existe
encore, n'est pas né après l'acte, l'agent le voit.

**Un locuteur ne se repose que sur une zone qui en porte un.** La route d'attribution le
refusait seule (422), et l'annulation, qui rejoue hors routes, le reposait : une bulle dont
on avait retiré le locuteur, passée en case par une collègue, le retrouvait EN TANT QUE CASE
au Ctrl+Z suivant. L'annulation d'un tel `delien` est désormais **passée** (seconde phrase,
« l'état d'avant ne peut plus être rétabli ») ; dans une suppression rétablie, le lien ne
revient pas et compte parmi les `liens_non_rendus`. Ce que la base portait avant cette règle,
`tools/retirer_locuteurs_muets.py` le montre, et le retire avec `--appliquer` — en acte
MACHINE, donc hors Ctrl+Z.

**Le miroir : ce qu'un type ne montre pas part avec lui** (ANN-8, demandé par Hugo le
2026-10-21). Une boîte personnage qui change de type perd son personnage montré, une case qui
devient zone de texte ou boîte personnage sa situation — invisibles sur une bulle, ils
comptaient encore au registre, dans la Recherche, l'Exploration et les exports. Même patron
que le locuteur : seulement sur un vrai changement de type, dans le même acte (son `avant`
porte `presence` et `attributs`, des identifiants), un seul Ctrl+Z les rend, la réponse le
dit (`presence_retiree`, le personnage ; `situation_retiree`, un NOMBRE de valeurs — un
terme peut être local à une collection qu'on ne lit pas), et l'annulation ne repose un
personnage montré que sur une boîte, une situation que sur une case. Le personnage montré
est gardé comme le locuteur (409 nommé, champ `presence`). La situation est un ENSEMBLE :
quand le type rendu la montre, ses valeurs reviennent par différence, à côté de celles
qu'un autre a mises entre-temps, comme les tags d'une annotation — rien n'est écrasé, donc
pas de garde ; quand il ne la montre pas, ce que la région porte doit être une partie de ce
que l'acte avait laissé, sinon 409 nommé, champ `situation`. Ce que la base portait déjà,
`tools/retirer_liens_caches.py` le montre et le retire. Leurs routes d'attribution gardent
le type depuis le 2026-10-22 (422 nommé), comme celle du locuteur ; lire et retirer restent
ouverts à tout type, pour nettoyer ce qu'une base d'avant porte.

**Une situation CACHÉE retirée par un changement de type revient avec Ctrl+Z** (relecture
de la suite d'ANN-8, S1 ; la doctrine des tags cachés, ci-dessous). Une case peut porter une
valeur locale à une collection que l'agent ne lit pas : passer la case en bulle la retire
avec le reste — la règle du type ne regarde pas la portée —, et le Ctrl+Z la perdait, la
valeur échouant à la question « l'agent la voit-il ? ». Le travail d'une autre collection
disparaissait par un geste qui ne le voyait pas. Pour l'annulation d'un changement de type,
une valeur que CE même acte a retirée est donc rendable dès qu'elle existe encore et n'est
pas née après l'acte, que l'agent la voie ou non. Une suppression rétablie garde la question
de la portée. Et ce qu'on ne voit pas ne se dit pas (S2) : la réponse du changement de type
ne compte que les valeurs visibles (`situation_retiree`), la pile ne dit « retrait de sa
situation » que si l'agent en voit une, et un 409 causé par une valeur cachée ne rend ni son
identifiant ni son auteur — « modifiée ailleurs ». Ce 409 dit pourtant qu'une valeur cachée
est LÀ (la phrase, avec une `valeur_actuelle` vide) : c'est un oracle de confirmation,
accepté parce qu'inévitable — ne pas refuser effacerait le travail de l'autre collection —,
et borné : il ne joue que sur une région que l'agent écrit, et ne nomme rien.

**Une valeur ne revient que de sa dimension d'alors** (R1). `attribut_valeur` n'a pas
d'`AUTOINCREMENT` : l'identifiant d'une valeur supprimée peut revenir à une valeur neuve, et
le témoin de la date (`_valeur_nee_apres`) ne voit rien dans la même seconde. Le changement
de type photographie donc la dimension de chaque valeur (`attributs_dimensions`, dans
`liens_vus` et avec le retrait), et l'annulation ne rend une valeur — cachée surtout, puisque
la portée ne la juge plus — que si elle est encore de cette dimension. **Ce qui reste
ouvert** : un identifiant repris dans la même seconde PAR UNE VALEUR DE LA MÊME DIMENSION ; et,
pour un changement de type journalisé avant cette photographie, la règle de la date seule.

**Le locuteur est un champ GARDÉ de l'annulation** (relecture croisée de ANN-8, 2026-10-21 ;
`undo._garder_liens_du_type`). Deux annulations d'un changement de type écrasaient le geste d'un
autre, sans 409. Alice passe la bulle de Tintin en case ; Bob la repasse en bulle et lui
donne Haddock ; le Ctrl+Z d'Alice remplaçait Haddock par Tintin — la garde du type passait,
le type étant déjà celui qu'elle rendait. Et Alice passe une case en bulle ; Bob lui donne
Haddock ; le Ctrl+Z d'Alice rendait une case qui parle. Dans les deux cas l'annulation est
désormais **refusée**, par le même 409 nommé qu'un enregistrement périmé (champ
`locuteur`, l'auteur du dernier `lien` qui l'a posé), et rien n'est écrit — retirer le
locuteur de Bob en silence aurait effacé son geste. Le même locuteur reposé ne bloque rien.
La garde compare des VALEURS, comme toutes celles de CONC-3 : Alice attribue Haddock, Bob
passe la bulle en case (Haddock part), Alice annule son attribution — sans effet, il n'y est
plus —, puis le Ctrl+Z de Bob rend la bulle ET Haddock. Rien n'a changé depuis l'acte de Bob,
donc rien n'est écrasé ; l'intention d'Alice ne se lit dans aucune valeur.

**La garde compare à ce que l'acte a VU, photographié par lui** (contre-relecture de ANN-8,
2026-10-21 ; `database.liens_vus`, `undo._garder_liens_du_type`). Elle comparait le locuteur
actuel à « aucun », faute de savoir ce que le changement de type avait trouvé. Sur une base
d'avant ANN-8, une case qui portait déjà le locuteur de la bulle qu'elle était, repassée en
bulle par une personne seule puis Ctrl+Z, recevait un 409 FAUX — « modifié ailleurs », ou
« depuis un autre écran de ce même compte » avec une date antérieure à l'acte. Chaque
changement de type photographie désormais, dans son `avant`, les liens qu'il voit, sous
`liens_vus` — une clé à part : `locuteur`, à côté, veut toujours dire « retiré ». Ce que
l'acte a LAISSÉ est la photographie moins ce qu'il a retiré, et c'est à elle que l'annulation
compare. Deux cas, selon le type rendu :

- il porte un locuteur, et l'acte avait retiré le sien : l'annulation le repose. Admis :
  aucun locuteur, ou celui-là ; un autre serait écrasé (Alice, Bob et Haddock, ci-dessus) ;
- il n'en porte pas : l'annulation ne repose rien. Admis : aucun locuteur, ou celui que
  l'acte avait laissé. Un autre deviendrait invisible ; aucun n'efface rien.

La photographie porte aussi le personnage montré et la situation, sous la même règle.

L'annulation rend donc l'état d'avant TEL QU'IL ÉTAIT : la case d'avant ANN-8 retrouve son
locuteur caché, et c'est `tools/retirer_locuteurs_muets.py` qui la nettoie — ce n'est pas le
rôle d'un Ctrl+Z. **Un changement de type journalisé avant la photographie n'a pas
`liens_vus`** : la garde y suppose, comme avant, qu'aucun locuteur n'était laissé, et le 409
faux y reste possible. Il ne disparaît, pour ces actes, qu'une fois l'outil passé.

**L'annulation d'une attribution est gardée elle aussi** (trouvé par Hugo à la QA du lot 1,
2026-10-23 ; `undo._garder_lien`). La garde ne valait que pour l'annulation d'un changement
de type : celle d'un `lien` ou d'un `delien` retirait ou reposait le lien sans regarder ce que
la région portait. Proprio donne Zed à une bulle ; Stagiaire le remplace par Yann ; le Ctrl+Z
de Proprio retirait Yann, et la bulle n'avait plus aucun locuteur — présent depuis D1, et le
même trou pour le personnage montré. L'annulation compare désormais ce que la région porte à
ce que l'acte y avait LAISSÉ — le personnage d'un `lien`, aucun pour un `delien` — et à ce
qu'elle laissera : l'un ou l'autre, rien ne se perd, et elle passe (Stagiaire est revenue à
Zed, ou a déjà retiré le locuteur). Deux autres états sont admis (relecture croisée du
2026-10-23). AUCUN, quand le personnage que l'acte avait laissé a été supprimé depuis : la
suppression l'a ôté par cascade, sans rien écrire au journal, et ce n'est le geste de
personne sur cette région — refuser bloquait une personne seule sur son propre Ctrl+Z. Et
ce qu'a laissé un geste PLUS RÉCENT du MÊME agent sur ce lien, PASSÉ depuis (« Ne s'annule
plus », ou « Passer ce geste »), si rien n'a touché le lien ensuite : sans quoi chacun de
ses gestes d'avant se refusait à son tour, face à son propre travail. Un geste passé après
le conflit d'un AUTRE n'y entre pas — le dernier geste sur le lien est alors celui de
l'autre, et le refus continue de le nommer. Hors de ces cas, le 409 nommé de CONC-3 — champ
`locuteur` ou `presence`, le personnage présent, l'auteur du dernier acte qui l'a posé ou
ôté, changements de type compris (`conflit.auteur_des_champs` lit `bulle_locuteur` et
`regions` ensemble) —, rien n'est écrit, et l'Atelier offre « Passer ce geste ».

**L'auteur d'un refus d'annulation ne se cherche qu'APRÈS l'acte défait** (relecture croisée
du 2026-10-23 ; le `depuis` de `conflit.auteur_du_champ`, passé par toutes les gardes de
`undo.py`). La recherche remontait tout le journal de l'identifiant : elle nommait un geste
d'avant l'acte comme une modification faite « depuis », et — sous la numérotation d'avant la
v30, où un identifiant se reprenait — l'auteur d'un ANCIEN objet, dans une collection que
l'agent ne lit pas : l'instantané d'une suppression porte le locuteur de la région
supprimée. Rien trouvé après l'acte : « modifié ailleurs ». La même borne vaut pour la garde
d'un changement de type, d'une création (son annotation et l'enfant qui y est rattaché
compris — un enfant né avant l'acte et rattaché depuis se dit donc « modifié ailleurs ») et
d'une modification de région, et pour la note.

**Une fusion de personnages faite depuis l'acte fait refuser l'annulation d'un lien
qu'elle a réaffecté — c'est assumé** (2026-10-23). La fusion réaffecte les locuteurs du
doublon à sa cible sans rien écrire sous `bulle_locuteur` : l'annulation voit un autre
personnage que celui que l'acte avait laissé, et refuse — « modifié ailleurs », même pour
une personne seule. Journaliser la fusion lien par lien rendrait chacun de ces liens
annulable un par un par Ctrl+Z, ce qui serait pire. Le geste se passe (« Passer ce geste »),
et le locuteur fusionné reste. L'ordre des gardes ne change pas : un
acte dont la région a quitté la portée de l'agent, a disparu ou n'est plus le même objet est
PASSÉ par la phrase d'AUTH-14, sans rien dire de ce qu'elle porte ; un lien qui ne se repose
plus sur le type de la région est passé (« l'état d'avant ne peut plus être rétabli ») avant
toute comparaison. Le refus ne joue donc que sur une région que l'agent écrit, dont il lit le
locuteur et son auteur.

**Une annotation se défait par différence, et non par instantané** (CONC-3, 2026-09-16).
Restaurer `avant` entier défaisait aussi ce qu'une autre personne avait fait sur l'AUTRE
champ entre-temps : mesuré à deux navigateurs, annuler une note rendait la liste de tags
d'avant, donc effaçait le tag posé par un collègue. La différence entre `avant` et `apres`
dit ce que l'acte a changé, et seul cela est défait. Tant que personne d'autre n'a touché
l'annotation, le résultat est exactement `avant`.

**L'annulation repose les tags PAR LEUR LIBELLÉ, et sans filtre de portée** — `_tag_a_rendre`
résout le libellé, sans jamais le recréer (cf. le point suivant). Depuis AUTH-11 (2026-09-24), la SAISIE fait l'inverse : taper
le nom d'un tag local à une collection qu'on ne lit pas ne l'attache plus (`socle._ensure_tags`
reçoit la portée). **L'asymétrie est voulue, et l'inverser casserait l'undo** : restaurer
n'est pas saisir. Le journal garde l'annotation ENTIÈRE, cachés compris, précisément pour que
Ctrl+Z ne fasse pas disparaître le travail d'une collection qu'on ne lit pas — la même raison
qui fait remettre ce qu'on cache à l'enregistrement (`_tags_caches`). Poser la garde de saisie
ici ferait de l'annulation l'outil qui efface ce que l'enregistrement protège ; un test le
verrouille dans les deux sens. La même doctrine vaut pour la situation cachée qu'un
changement de type a retirée (cf. le miroir du locuteur, plus haut) : Ctrl+Z la rend.

**L'annulation ne CRÉE jamais de tag** (ANN-8, relecture croisée du 2026-10-22). Un tag se
renomme, se fusionne et se supprime depuis le panneau 📖 Lexique ; l'instantané d'une
annotation, lui, nomme ses tags par le libellé qu'ils avaient au moment de l'acte. L'ancien
`_ensure_tag` créait le libellé manquant : un Ctrl+Z d'un geste antérieur faisait revenir
un libellé LOCAL en tag GLOBAL, visible de toute l'instance, ou ressuscitait un tag supprimé
exprès. **Seuls les libellés de l'INSTANTANÉ de l'acte** (`avant` ∪ `après`) se résolvent ;
les tags que la région porte aujourd'hui se reposent par leur IDENTIFIANT, tels qu'ils sont —
un « x » posé depuis par un autre n'est pas l'ancien « x » renommé (contre-relecture du
2026-10-22). `_tag_a_rendre`, pour un libellé de l'instantané : (1) la chaîne du journal
`tags` APRÈS l'acte annulé — un renommage ou une fusion mène au libellé suivant, une
suppression arrête tout —, par les libellés des charges et l'ordre des événements, jamais
par l'identifiant seul (ceux de `tags` se réattribuent) ; (2) si la chaîne n'a rien changé,
le LIBELLÉ EXACT, lisible ou non — un tag caché revient comme il était, cacher n'est pas
saisir ; (3) sinon la clé (`cle_tag`), parmi les seuls tags que l'agent VOIT
(`clause_terme`, demandée par le `ecrivable` de la route sous la clé `tags`) : deux lignes
d'avant de même clé, l'une locale à une collection qu'il ne lit pas, ne lui font pas poser
celle-là. Un tag fusionné depuis se retire ou revient sous le nom de sa cible, un tag renommé
sous son nouveau nom. **Ce qui ne se résout pas ne revient pas** : quand la région revient
quand même (une suppression défaite, une annotation dont d'autres champs changent), le tag
manquant est compté à part, `tags_non_rendus` (`liens_non_rendus` garde son sens : locuteur,
personnage montré, attributs) ; quand l'acte ne portait QUE sur de tels tags, il n'y a rien à
rétablir, et l'acte est PASSÉ par la seconde phrase d'AUTH-14 (« l'état d'avant ne peut plus
être rétabli »). Un tag du même nom créé après la suppression n'est pas celui de l'acte, et
n'est pas rendu.

**Une annulation qui écraserait le geste d'un autre est refusée** (CONC-3, second temps,
2026-09-17). Annuler une modification de région réécrivait TOUTES ses colonnes depuis
`avant` : A déplaçait une bulle, B la transcrivait, A faisait Ctrl+Z, et le texte de B
disparaissait avec le déplacement — lu dans le code, puis vu rouge par un test. L'inverse ne
touche plus que les colonnes que l'acte a changées. Et si l'une d'elles — ou la note, pour
une annotation — ne porte plus la valeur que l'acte avait posée, l'annulation répond par le
même **409 nommé** qu'un enregistrement périmé (`conflit.py`) : qui a changé le champ, et
quand. Seul, rien ne change : personne n'a touché le champ depuis. Un changement fait par un
MOTEUR ne bloque pas (l'OCR n'est qu'un pré-remplissage). L'ordre et la source ne sont pas
gardés : l'ordre se recalcule, la source suit la retouche. La même règle refuse d'annuler la
CRÉATION d'une région que quelqu'un d'autre a travaillée depuis : la supprimer emporterait
son travail, et l'annulation ne garde aucun instantané de ce qu'elle supprime.

**Ses LIENS comptent aussi** (CONC-4, 2026-10-25 ; reproduit par la relecture croisée d'ANN-8
le 2026-10-21, `test_h5_…`). La garde de la création ne regardait que les colonnes,
l'annotation et les enfants : le locuteur, le personnage montré et la situation qu'un autre
avait donnés à la région partaient avec elle, par cascade. `_garder_liens_de_creation`
cherche, pour chaque lien que la région porte, l'acte qui l'a posé APRÈS la création
(`conflit.auteur_des_champs`, changements de type compris pour un locuteur ou un personnage) :
de l'auteur de la création, il passe — la situation ne s'annule pas, et la poser sur sa
propre case ne doit pas rendre sa création inannulable ; d'un autre, ou d'aucun acte (un
outil, une base retouchée : le journal nomme, il ne décide pas), c'est le 409 nommé, rien
d'écrit, et « Passer ce geste ». Seul compte ce qui RESTE : un lien posé puis retiré par un
autre ne bloque rien. L'autre case de la même relecture — annuler un `lien` ou un `delien`
de locuteur écrasait celui qu'un autre avait posé depuis — était déjà fermée par
`_garder_lien` (`a59e610`, puis `5c749d5`).

**Après un tel refus, l'acte RESTE en tête de la pile — et défaire à la main le geste de
l'autre n'en sort pas** (relevé par la contre-relecture d'ANN-8, 2026-10-21). Le 409 n'écrit
rien, pas même la trace qui PASSE un acte (cf. plus bas) : le Ctrl+Z suivant retombe sur le
même acte, et redonne le même 409 tant que la valeur de l'autre est là. Le réflexe est de la
retirer soi-même pour pouvoir annuler — Alice passe une case en bulle, Bob lui donne
Haddock, le Ctrl+Z d'Alice est refusé ; elle retire Haddock à la main, puis refait Ctrl+Z.
C'est un piège : ce retrait est un geste d'Alice, PLUS RÉCENT que son changement de type, et
c'est lui que le Ctrl+Z suivant défait d'abord. Haddock revient, et au Ctrl+Z d'après, le
même 409. La pile d'Alice reste bloquée sur cet acte, et ses gestes plus anciens hors de
portée de Ctrl+Z. C'est vrai de tout refus de ce paragraphe, pas seulement du locuteur :
retaper à la main le texte qu'un autre a remplacé, remettre une position, recrée le même
cercle.

Ce qui en sort :

- **« Passer ce geste »** (décision de Hugo du 2026-10-22) : le message du refus, dans
  l'Atelier, porte ce bouton. Le serveur (`POST /api/undo/passer`, avec l'acte que le 409 a
  désigné sous `passable` — l'acte que l'annulation a relu et refusé sous le verrou
  d'écriture, joint au refus) pose la trace `abandon` d'AUTH-14 — l'acte sort de la pile, le
  Ctrl+Z suivant remonte au geste d'avant, et le travail de l'autre RESTE. Deux gardes, sous
  le verrou : l'acte est bien le prochain que CET agent annulerait (ni celui d'un autre, ni
  un acte enfoui sous un plus récent) ; et le conflit tient au moment du clic — l'annulation
  est rejouée puis défaite, et si elle passe désormais, rien n'est passé : « refaites
  Ctrl+Z ». Passer est définitif, comme tout acte passé ;
- **que l'autre défasse son propre geste** : son Ctrl+Z à lui (ou le retrait qu'il fait) n'est
  pas un acte d'Alice, et le Ctrl+Z suivant d'Alice passe — la valeur n'est plus là ;
- **faire à la main ce que Ctrl+Z aurait fait** — remettre le type, la note, la position —,
  sachant que c'est un geste neuf, écrit au journal sous son nom, et qu'il ne débloque pas la
  pile : deux Ctrl+Z plus loin, le même refus — sauf à passer ensuite l'acte refusé ;
- sinon, laisser l'acte : un 409 ne change rien à la base.

**Recréation à l'identique** : l'instantané profond porte les `id` d'origine → citations,
deep-links et références restent valides. Si un `id` a été **réattribué** depuis (une nouvelle
région a pris la place libérée), l'acte est **passé** (cf. ci-dessous) plutôt que d'écraser —
il n'est plus un 409 qui revient à chaque Ctrl+Z. Depuis la v30, un identifiant ne se
réattribue plus ; le cas reste possible pour les actes d'avant elle (cf. ci-dessous).

## Ajustement A3 : les annotations ciblent `region_id`

Les événements d'annotation ciblaient l'`ann_id` (id d'annotation), **détruit** à la
suppression → une annotation supprimée aurait été irrécupérable. Ils ciblent désormais le
**`region_id`** (stable, `region_id` est UNIQUE dans `annotations`), comme locuteur/présence.
Additif : l'export PROV keye simplement l'entité annotation par sa région.

## Périmètre

**Inclus** : région (créer / modifier / supprimer+cascade), annotation (note + tags), locuteur,
présence — les gestes d'annotation, dont le plus destructeur. **Actes MACHINE non annulables**
par l'utilisateur (`agent_type='moteur'` filtré : une passe ML se rejoue, elle ne s'annule pas
au clavier). **Hors périmètre (dormant)** : correction grammaticale (tokens), validation
planche/région, et le **redo**.

## À qui appartient l'annulation (AUTH-2)

**Ctrl+Z est un geste PERSONNEL : chacun n'annule que ses propres actes**, administrateur
compris. Annuler l'acte d'un collègue à son insu serait une surprise, pas une
fonctionnalité — et un administrateur qui veut défaire le travail d'un autre a le journal
pour le lire, pas Ctrl+Z pour l'effacer.

En mono-poste (`BD_AUTH_PROXY` absent), rien ne change : il n'y a qu'une personne, tous les
actes portent le même agent `NULL`, et aucun filtre ne s'applique. La sentinelle `undo.TOUS`
distingue « ne pas filtrer » de « filtrer sur l'agent anonyme », qui est une valeur légitime.

**Et c'est le seul filtre possible**, ce qui mérite d'être compris plutôt que subi. Le reste
de l'application se cloisonne par collection ; l'annulation ne le peut pas. Scoper par
collection supposerait de remonter de l'événement à sa région, puis à son album — or l'acte
qu'on a le plus besoin d'annuler est justement une **suppression**, dont la cible n'existe
plus. Le journal survit à sa cible (`cible_id` n'est pas une FK, c'est tout le principe) ;
un filtre par album rendrait donc l'annulation d'une suppression impossible, c'est-à-dire
l'inverse du service rendu.

Viser un événement par son `id` ne contourne pas la règle : `undo.annuler` revérifie
l'agent.

**Un plancher d'écriture, et une garde sur le lieu même** (AUTH-14, 2026-10-15).
`POST /api/undo` exige toujours un droit d'écriture quelque part : annuler REJOUE une
écriture. Mais ce plancher ne dit pas OÙ, et la décision du 2026-08-28 assumait le reste —
« quelqu'un qui écrit dans B peut encore annuler son propre acte passé sur A ». Elle tenait
que le fermer supposait de retrouver l'album d'une cible disparue, et qu'un contrôle d'accès
dépendant de la forme d'un JSON journalisé serait plus fragile que le trou.

Le trou était plus large qu'on ne le croyait, et c'est ce qui a rouvert la décision : les
identifiants se réattribuaient (cf. ci-dessous), si bien qu'un acte pouvait désigner une
région d'une AUTRE collection, que son auteur n'avait jamais touchée. Et la garde se pose
sans dépendre du JSON là où la cible existe : l'inverse d'un acte autre qu'une suppression
écrit dans une région PRÉSENTE, que l'accesseur gardé juge en écriture, sous la portée de la
requête. Pour rétablir une suppression, il juge la planche où la région reviendrait — lue,
elle, dans l'instantané, mais c'est le même instantané que la recréation lit déjà : sans lui,
il n'y a rien à rétablir. `undo.annuler` exige ce jugement (`ecrivable`, sans défaut, comme
la `Portee` des accesseurs).

Ce qui en résulte : une personne RETIRÉE d'une collection, ou rétrogradée en lecture,
n'y annule plus rien.

## Un identifiant repris n'est pas le même objet (AUTH-14)

Sans `AUTOINCREMENT`, la région créée après la suppression de celle d'identifiant le plus
haut reprend cet identifiant — dans n'importe quelle collection ; une planche aussi. Le
`cible_id` d'un acte désignait alors un objet que son auteur n'avait jamais touché. Mesuré
le 2026-10-14 : le Ctrl+Z d'une collègue effaçait un locuteur de l'Incubateur, où elle
n'entre pas ; le 409 du conflit de version lui rendait le texte de la région et le login de
son auteur ; et un acte sur un identifiant repris revenait en 409 à chaque Ctrl+Z.

**Depuis la v30 (2026-10-16), les identifiants ne reviennent plus** : `albums`, `planches`,
`regions` et `personnages` portent `AUTOINCREMENT`, et la migration a amorcé chaque compteur
au-dessus du plus grand identifiant que le journal ait jamais nommé (cf. `CLAUDE.md`,
§ Schéma & migrations). Les témoins qui suivent RESTENT pourtant, pour deux raisons : les
actes d'avant la v30 désignent des identifiants qui ont pu être repris avant elle ; et un
identifiant peut encore revenir hors de tout chemin ordinaire — rendu par une transaction
défaite (SQLite défait aussi l'avance du compteur), ou posé à la main en base. Les tests de
cette garde ramènent leur base à la numérotation d'avant pour la mesurer encore : une défense
en profondeur que rien ne doit désarmer en silence.

Avant toute écriture, l'annulation vérifie donc que l'objet est le MÊME (`undo._meme_objet`),
par quatre témoins, dont aucun ne suffit seul — chacun a son test, qui tombe quand on
l'éteint :

- **le journal, côté création** : aucune création de région sous cet identifiant depuis
  l'acte. Toute création par une route ou par une passe ML est journalisée ; rétablir une
  suppression ne l'est pas comme création — c'est le même objet qui revient ;
- **le journal, côté suppression** : aucune suppression de la région — directe, ou par
  l'instantané d'un ancêtre — postérieure à l'acte et NON annulée. Une suppression annulée
  ne compte pas : son annulation a rendu le même objet ;
- **la planche au moment de l'acte**, lue dans le dernier instantané qui la porte, sans
  remonter au-delà d'une suppression (avant elle, le journal parle d'un autre objet) — pour
  les régions nées sans événement de création (la segmentation lancée à l'import ShareDocs
  n'en écrit pas) ;
- **l'album** de la planche, s'il a été importé APRÈS l'acte : seul témoin d'une planche
  reprise, que rien ne journalise.

Le **parent** est un objet lui aussi. L'inverse d'une modification le rend validé comme la
route le valide (`socle._validate_parent` : présent, même planche, pas de cycle), et les
témoins le jugent : repris ailleurs ou supprimé depuis, il n'est plus celui de l'acte. Sans
quoi Ctrl+Z rattachait une bulle à une case d'une autre collection, que la suppression de
cette case emportait ensuite et que son rétablissement recréait (relecture croisée,
2026-10-15). Pour rétablir une suppression : identifiants libres, planches de TOUS les nœuds
présentes et nées avant l'acte — un enfant peut vivre hors de la planche de son parent dans
une base retouchée avant ce correctif —, parent dans la même planche, ni recréé ni supprimé
depuis ; et la garde d'écriture porte sur chacune de ces planches.

Le **personnage** qu'un lien reposerait aussi : ses identifiants se réattribuaient avant la
v30, et l'acte
n'en garde que l'identifiant — le journal ne trace ni la création ni la suppression d'un
personnage. Deux témoins restent : il doit être VU de l'agent (ses apparitions, la règle des
personnages), et ne pas avoir été créé après l'acte (`personnages.date_creation`).

**Un acte qui ne s'annule plus est PASSÉ, pas bloquant.** Objet disparu, identifiant repris,
collection qu'on n'écrit plus, état d'avant qui n'a plus où se poser (parent disparu ou qui
ferait un cycle, personnage supprimé — la clé étrangère qui échouait renvoyait le même 409 à
chaque Ctrl+Z) : l'annulation défait ce qu'elle aurait commencé d'écrire, écrit une trace
append-only (`type = 'abandon'`, `cible_table = 'annulation'`, `cible_id` = l'acte) qui le
sort de la pile, et répond 409. Le Ctrl+Z suivant défait le geste d'avant. La trace n'est pas
une `annulation` : rien n'a été défait, et `conflit.auteur_du_champ` lit une annulation comme
ayant reposé l'état `avant`. Elle est RETENUE hors du dépôt (`tools/_commun.CIBLES_RETENUES`)
et ne compte pas parmi les actes d'un compte (`comptes.traces`) : elle n'a rien produit. Elle
est validée malgré le refus — sans elle, le même 409 reviendrait.

**Deux phrases, et rien de l'objet présent.** Le refus ne porte ni valeur, ni auteur, ni
texte d'erreur SQL.

- « Ne s'annule plus : *geste* — la région n'est plus à votre portée. » quand la région, ou
  sa place, n'est plus celle de l'acte ou plus à portée d'écriture. Elle ne distingue pas
  « disparue » de « reprise » ni de « hors d'écriture » : deux phrases diraient à qui ne lit
  plus la planche ce qu'il est advenu d'elle, ce que le 404 garde partout ailleurs.
- « Ne s'annule plus : *geste* — l'état d'avant ne peut plus être rétabli. » quand la région
  est bien à portée, mais que ce qu'elle retrouverait n'a plus où se poser — parent,
  personnage. L'agent écrit la région : elle ne lui apprend rien qu'il ne puisse lire, et
  elle ne dit pas si le personnage existe.

Là où l'agent écrit la région, le conflit de version (409 nommé, valeur et auteur) est
inchangé.

**Un acte passé ne revient pas, même si l'objet revient.** C'est voulu, et la règle reste
simple. Le scénario, relevé par la relecture croisée : la collègue modifie le texte d'une
région ; l'importatrice supprime la région ; la collègue fait Ctrl+Z — la région n'est plus
là, l'acte est passé ; l'importatrice rétablit sa suppression, la région revient, la même ;
un nouveau Ctrl+Z de la collègue ne revient PAS sur sa modification, il remonte au geste
d'avant. Le rendre annulable de nouveau supposerait qu'une trace s'efface ou se périme, donc
une pile qui dépend d'états qu'on ne voit pas ; et ce que la collègue a perdu est un raccourci
— elle peut toujours retaper son texte. Même chose si le droit d'écrire revient.

**Ce qui n'est pas fermé.**

- **La même seconde** : les dates sont à la seconde ; une planche reprise dans un album
  importé dans la seconde même de l'acte, ou un personnage créé dans cette seconde, ne sont
  pas vus.
- **Une planche reprise dans un album importé AVANT l'acte** — n'importe lequel, de
  n'importe quelle collection, et pas seulement le même album : quand on rétablit une
  suppression, aucun témoin ne voit que la planche n'est plus celle de l'acte. La garde
  d'écriture tient toujours — on n'écrit que là où l'on écrit —, c'est l'identité qui manque.
- **Une région disparue SANS événement** (une re-passe ML remplace les régions machine sans
  en journaliser la suppression) puis reprise sans événement, dans la même planche : aucun
  témoin ne la voit.
- **Fermé du côté sûr** : une région reprise puis supprimée, l'originale rétablie ensuite,
  passe pour reprise — Ctrl+Z refuse là où il aurait pu agir.
- Rendre les identifiants non réutilisables était une autre décision, attendue avec une
  migration ; cette garde tenait sans elle. C'est fait par la v30 (2026-10-16), pour les
  identifiants nés après elle : les trous ci-dessus ne concernent plus que les actes
  d'avant, et un identifiant revenu hors des chemins ordinaires.

## Un compte COLLECTIF : un délai de cinq minutes (AUTH-6)

Sous un login **partagé** — un groupe d'étudiants, un compte de démonstration, déclarés
`collectif` dans la vue des comptes —, le filtre par agent ne sépare plus « mes actes » de
ceux du collègue qui tape sous le même login : l'application ne voit que `Remote-User`, et
lui donner de quoi distinguer deux personnes reviendrait à fabriquer de l'identité, ce
qu'AUTH-1 lui interdit. Ctrl+Z n'y remonte donc que les **cinq dernières minutes**
(`undo.DELAI_COLLECTIF_MINUTES`, tranché le 2026-09-11).

**Le temps, et non la session** : l'application n'a aucune notion de session et ne doit
pas s'en fabriquer une ; et le vrai risque n'est pas de défaire ce qu'un autre a fait il y
a trente secondes, mais avant la pause. La borne vaut pour l'aperçu comme pour
l'exécution, et **viser un acte par son `id` ne la contourne pas** — nommer un acte ne le
rajeunit pas. Au-delà, le refus le DIT (« Rien à annuler dans les 5 dernières minutes : sur
un compte partagé… ») plutôt que de laisser croire l'historique vide.

**C'est la DÉCLARATION qui déclenche la borne**, et c'est ce qu'il faut savoir pour qu'elle
serve : un login partagé que personne n'a déclaré `collectif` est lu comme nominatif, et
garde un Ctrl+Z sans limite. L'application ne peut pas deviner qu'un login est partagé —
c'est précisément ce qu'elle ne voit pas.

Un compte **nominatif** garde tout son historique, et le mono-poste n'a aucun délai. Ce qui
reste vrai sous un compte collectif, et c'est la borne du remède : **dans** les cinq
minutes, deux personnes sous le même login peuvent encore défaire l'une l'acte de l'autre.
Le délai réduit la fenêtre, il ne sépare pas les personnes — rien ne le peut ici.

## Boucle

- **API** : `GET /api/undo/prochain` (aperçu : `{evenement_id, description}` ou `null`) ·
  `POST /api/undo` (exécute ; renvoie `{description, acte, cible_table, region_id, planche_id}` ;
  **404** si rien à annuler, **409** si l'inverse est impossible — avec `detail.ecarte` quand
  l'acte a été passé, et `detail.message` pour la phrase que l'Atelier affiche).
- **UI** : **Ctrl/⌘+Z** dans la Visionneuse (hors champ de saisie — dans un champ, l'undo natif
  du navigateur s'applique) → toast « Annulé : … » + rafraîchissement de la planche/région
  touchée. Une sauvegarde d'annotation différée en attente est **annulée** (pas flushée) avant
  l'undo, pour ne pas ré-appliquer un buffer périmé.
