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
| `suppression` région | **recréer le sous-arbre** depuis l'instantané profond (région + annotation + enfants, **mêmes `id`**) |
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
région a pris la place libérée), l'annulation échoue proprement en **409** plutôt que d'écraser.

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

**Un plancher d'écriture, et un résiduel assumé.** `POST /api/undo` exige en plus un droit
d'écriture quelque part : annuler REJOUE une écriture, et le filtre par agent seul laissait
quelqu'un rétrogradé en lecture seule défaire ses anciens actes.

Ce plancher ne dit pas SUR QUELLE collection portait l'acte. Quelqu'un qui écrit dans la
collection B peut donc encore annuler son propre acte passé sur A, où il n'écrit plus.
Décision du 2026-08-28 : **on l'assume plutôt que de le fermer.** Le fermer supposerait de
retrouver l'album de la cible — impossible pour une suppression, dont la cible n'existe
plus. On pourrait le lire dans l'instantané profond que porte l'événement, mais un contrôle
d'accès qui dépend de la FORME d'un JSON journalisé est plus fragile que le trou qu'il
bouche. Le scénario reste étroit : il faut avoir eu le droit, l'avoir perdu, et n'annuler
que ses propres actes.

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
  **404** si rien à annuler, **409** si l'inverse est impossible).
- **UI** : **Ctrl/⌘+Z** dans la Visionneuse (hors champ de saisie — dans un champ, l'undo natif
  du navigateur s'applique) → toast « Annulé : … » + rafraîchissement de la planche/région
  touchée. Une sauvegarde d'annotation différée en attente est **annulée** (pas flushée) avant
  l'undo, pour ne pas ré-appliquer un buffer périmé.
