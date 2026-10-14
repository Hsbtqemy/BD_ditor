---
chantier: AUTH-14
statut: livré
---

# AUTH-14 — Ctrl+Z ne traverse plus le cloisonnement des collections

**Arrêté sur** — 2026-10-15, `f436aa1` : **Ctrl+Z n'écrit plus que là où l'on écrit, ne rend
plus rien de ce qu'on ne lit pas, et ne bloque plus sa pile.** Écrit et relu sur une copie,
porté sur `dev` la nuit du 14 au 15 octobre ; ce qui reste ouvert est écrit dans
`docs/undo.md` et dans le `Reste` ci-dessous.

## Reste

### Ce que le correctif laisse, écrit dans `docs/undo.md`

- [ ] **Une planche reprise dans un album importé AVANT l'acte se reconnaît au rétablissement
  d'une suppression** — attendu : fermé, ou fermé par la v30. Aucun témoin ne la voit ; la
  garde d'écriture tient toujours (on n'écrit que là où l'on écrit), c'est l'IDENTITÉ de
  l'objet qui manque
- [ ] **Une région disparue sans événement, puis reprise sans événement dans la même planche,
  se reconnaît** — attendu : fermé, ou fermé par la v30. Une re-passe automatique supprime et
  recrée des régions sans les journaliser une à une ; l'import ShareDocs vers un album existant
  segmente sans aucun événement
- [ ] **Une reprise dans la même seconde que l'acte se reconnaît** — attendu : dit, ou fermé.
  Les témoins de l'album et du personnage comparent des dates à la seconde
- [ ] **Les identifiants ne se réutilisent plus** — attendu : tranché par Hugo, avec la v30
  (cf. `COL-3`, zone « Tranche 2 — relevé par son deuxième commit »). C'est la cause de tout ce
  chantier : `regions`, `planches`, `albums` et `personnages` rendent l'identifiant d'un objet
  détruit au suivant, et tout identifiant gardé par le journal peut alors désigner un autre
  objet. Les témoins de ce correctif en rattrapent les effets connus ; ils ne la suppriment pas
- [ ] **`CLAUDE.md` dit ce que l'annulation vérifie** — attendu : réécrit. « L'annulation se
  filtre par AGENT et non par collection » ne suffit plus : elle n'écrit aussi que là où l'agent
  écrit MAINTENANT, reconnaît une cible qui n'est plus celle de l'acte, et passe un acte
  inannulable par une trace retenue de toute sortie, définitivement

## Contexte

### D'où cela vient

Trouvé le 2026-10-14 par la relecture croisée de la tranche 2 de `COL-3`, puis rejoué sur
`5311ccc`, donc présent en production : sans `AUTOINCREMENT`, la région créée après la
suppression de la dernière reprend son identifiant, dans n'importe quelle collection. Ctrl+Z,
filtré par agent et non par collection, appliquait alors l'inverse d'un ancien acte à cette
région-là : un locuteur effacé, une région supprimée, une bulle rattachée à une case d'une
autre collection — ou, dans le refus d'un conflit de version, le texte de cette région et le
login de son auteur. Aucune destruction d'album n'était nécessaire : il suffisait qu'un autre
membre supprime la dernière région créée. Une personne retirée d'une collection pouvait aussi
annuler son dernier acte dedans. Et un acte inannulable bloquait la pile, chaque Ctrl+Z
retombant dessus. Hugo a voulu le correctif dans le lot en cours, avant la fusion vers `main`.

### Ce que fait le correctif

Avant toute écriture, l'annulation pose deux questions. Peut-on écrire, MAINTENANT, à chaque
endroit que l'inverse touche — la région, la planche de chaque nœud d'une suppression rétablie,
le parent rendu, le personnage reposé ? L'objet est-il encore celui de l'acte ? Quatre témoins
en jugent sans changer le schéma : aucune création journalisée sous cet identifiant depuis
l'acte ; la planche au moment de l'acte ; l'album importé après l'acte ; une suppression
journalisée depuis l'acte et non annulée. Un personnage, lui, doit être vu de l'agent et né
avant l'acte. Un parent rendu se valide comme la route le valide.

Si l'une des réponses est non, ou si une contrainte de la base refuse l'inverse, l'acte est
PASSÉ : une trace append-only (`type='abandon'`, `cible_table='annulation'`) le sort de la pile,
retenue de toute sortie et hors du compte des actes laissés par un compte, et le Ctrl+Z suivant
défait le geste d'avant. Deux phrases seulement, qui ne disent rien de l'objet : « Ne
s'annule plus : *geste* — la région n'est plus à votre portée », et « … — l'état d'avant ne
peut plus être rétabli ». Une seule pour tout ce qui est hors de portée : deux diraient à qui
ne lit plus la planche si la région a été supprimée ou si elle vit encore ailleurs. Là où
l'agent lit et écrit, le conflit de version (`CONC-3`) est inchangé.

Un acte passé ne revient pas, même si l'objet est rétabli plus tard : la règle reste simple,
et rien de faux n'est écrit. C'est un changement par rapport à avant, mesuré par la relecture.

### Ce qui l'a éprouvé

Deux tours. L'auteur : 19 tests d'abord (17 rouges sur `5311ccc`), 16 mutants tombés ; trois
variantes trouvées en route (annuler une création supprimait la région de l'autre collection,
deux rétablissements écrivaient au mauvais endroit). La relecture croisée : « portable après
corrections » — le changement de parent traversait encore, l'erreur de clé étrangère bloquait
la pile, un témoin manquait, la trace comptait comme un acte, trois de ses mutants
survivaient, un personnage repris n'était pas reconnu. Corrigé en six commits, chacun tenu par
un test rouge puis vert et par ses mutants (17, tous tombés), puis les sondes de la relecture
rejouées contre la tête corrigée : toutes fermées sauf deux résiduels écrits, et la sortie de la pile, qui reste définitive par décision. Suite par défaut : 1 705 passés sur `dev` après le
portage. Tests navigateur du Ctrl+Z (annotation, conflit à deux, accessibilité) : 43 verts.
