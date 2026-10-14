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
| `creation` région | supprimer la région (+ sous-arbre, désindexé) — **refusé** si quelqu'un d'autre l'a modifiée, annotée ou y a rattaché une région depuis |
| `modification` région (géométrie / OCR / déplacement) | remettre les colonnes que l'acte a CHANGÉES à leur valeur `avant` — **refusé** si l'une d'elles a changé depuis (sauf par un moteur) |
| `suppression` région | **recréer le sous-arbre** depuis l'instantané profond (région + annotation + enfants, **mêmes `id`**) — **passé** si un `id` a été repris, si la planche ou le parent n'est plus le même, ou si l'on n'écrit plus dans la planche |
| `creation` / `modification` / `suppression` annotation | défaire ce que l'acte a CHANGÉ, sur l'état actuel : la note revient à `avant` si l'acte l'a changée ; les tags qu'il a ajoutés partent, ceux qu'il a retirés reviennent ; vide, l'annotation est supprimée |
| `lien` locuteur/présence (avant ∅) | retirer le lien |
| `lien` (avant présent) / `delien` | rétablir l'ancien lien |

**Une annotation se défait par différence, et non par instantané** (CONC-3, 2026-09-16).
Restaurer `avant` entier défaisait aussi ce qu'une autre personne avait fait sur l'AUTRE
champ entre-temps : mesuré à deux navigateurs, annuler une note rendait la liste de tags
d'avant, donc effaçait le tag posé par un collègue. La différence entre `avant` et `apres`
dit ce que l'acte a changé, et seul cela est défait. Tant que personne d'autre n'a touché
l'annotation, le résultat est exactement `avant`.

**L'annulation repose les tags PAR LEUR LIBELLÉ, et sans filtre de portée** — `_ensure_tag`
résout le libellé ou le recrée. Depuis AUTH-11 (2026-09-24), la SAISIE fait l'inverse : taper
le nom d'un tag local à une collection qu'on ne lit pas ne l'attache plus (`socle._ensure_tags`
reçoit la portée). **L'asymétrie est voulue, et l'inverser casserait l'undo** : restaurer
n'est pas saisir. Le journal garde l'annotation ENTIÈRE, cachés compris, précisément pour que
Ctrl+Z ne fasse pas disparaître le travail d'une collection qu'on ne lit pas — la même raison
qui fait remettre ce qu'on cache à l'enregistrement (`_tags_caches`). Poser la garde de saisie
ici ferait de l'annulation l'outil qui efface ce que l'enregistrement protège ; un test le
verrouille dans les deux sens.

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

**Recréation à l'identique** : l'instantané profond porte les `id` d'origine → citations,
deep-links et références restent valides. Si un `id` a été **réattribué** depuis (une nouvelle
région a pris la place libérée), l'acte est **passé** (cf. ci-dessous) plutôt que d'écraser —
il n'est plus un 409 qui revient à chaque Ctrl+Z.

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
identifiants se réattribuent (cf. ci-dessous), si bien qu'un acte pouvait désigner une
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

Avant toute écriture, l'annulation vérifie donc que l'objet est le MÊME (`undo._meme_objet`),
par trois témoins, dont aucun ne suffit seul :

- **le journal** : aucune création de région sous cet identifiant depuis l'acte. Toute
  création par une route ou par une passe ML est journalisée ; rétablir une suppression ne
  l'est pas comme création — c'est le même objet qui revient ;
- **la planche au moment de l'acte**, lue dans le dernier instantané qui la porte — pour
  les régions nées sans événement de création (la segmentation lancée à l'import ShareDocs
  n'en écrit pas) ;
- **l'album** de la planche, s'il a été importé APRÈS l'acte : seul témoin d'une planche
  reprise, que rien ne journalise.

Pour rétablir une suppression : identifiants libres, planche présente et née avant l'acte,
parent — s'il y en a un — dans la même planche et jamais recréé.

**Un acte qui ne s'annule plus est PASSÉ, pas bloquant.** Objet disparu, identifiant repris,
collection qu'on n'écrit plus : l'annulation écrit une trace append-only (`type = 'abandon'`,
`cible_table = 'annulation'`, `cible_id` = l'acte) qui le sort de la pile, et répond 409 avec
une seule phrase — « Ne s'annule plus : *geste* — la région n'est plus à votre portée. » Le
Ctrl+Z suivant défait le geste d'avant. La trace n'est pas une `annulation` : rien n'a été
défait, et `conflit.auteur_du_champ` lit une annulation comme ayant reposé l'état `avant`.
Elle est RETENUE hors du dépôt (`tools/_commun.CIBLES_RETENUES`) : elle n'a rien changé au
corpus. Elle est validée malgré le refus — sans elle, le même 409 reviendrait.

**Une phrase pour tous les cas, et rien de l'objet présent.** Le refus ne porte ni valeur
ni auteur : la région visée n'est peut-être plus lisible. Et il ne distingue pas « disparue »
de « reprise » ni de « hors d'écriture » — deux phrases diraient à qui ne lit plus la planche
ce qu'il est advenu d'elle, ce que le 404 garde partout ailleurs. Là où l'agent écrit la
région, le conflit de version (409 nommé, valeur et auteur) est inchangé.

**Ce qui n'est pas fermé.**

- **La même seconde** : les dates sont à la seconde ; une planche reprise dans un album
  importé dans la seconde même de l'acte n'est pas vue par le troisième témoin.
- **Une planche reprise DANS LE MÊME album**, par une région née sans événement : aucun
  témoin ne la voit. La garde d'écriture tient toujours — on n'écrit que là où l'on écrit —,
  c'est l'identité qui manque.
- **Fermé du côté sûr** : une région reprise puis supprimée, l'originale rétablie ensuite,
  passe pour reprise — Ctrl+Z refuse là où il aurait pu agir. Et une trace est définitive :
  un acte passé parce qu'on n'écrivait plus ne revient pas si le droit revient.
- Rendre les identifiants non réutilisables est une autre décision, attendue avec une
  migration ; cette garde tient sans elle.

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
