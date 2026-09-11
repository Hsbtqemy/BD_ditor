---
passe: Un terme qu'on ne lit pas ne se voit pas
chantier: AUTH-11
duree: 25 min
---

# QA — un tag ou une dimension d'une collection qu'on ne lit pas ne sort nulle part

La suite verrouille les routes : chaque lecture, sous deux identités, et chaque oracle
comparé à un identifiant absent. Ce que la passe regarde, c'est qu'aucun ÉCRAN n'en montre
davantage que les routes — un nuage, une puce, une liste d'axes — et que l'écriture
préserve ce qu'elle cache, ce qui ne se voit qu'en regardant le travail de l'autre après
coup.

**Sur la pile locale**, `https://bd.127-0-0-1.sslip.io`. Elle suppose la passe *Le droit
d'exporter, à l'écran* jouée au moins jusqu'à la création d'« Étude B » : `proprio`
possède « Collection Test » et « Étude B », l'album esther v1 vit dans les deux,
`lectrice` lit « Collection Test » par le groupe `annotateurs`, `stagiaire` y écrit.
Si `lectrice` a reçu la lecture sur « Étude B » dans cette autre passe, la retirer d'abord
— sans quoi elle lit ce que la passe veut lui cacher.

**Décor** (sous `proprio`, ~5 min) :

1. *Atelier*, esther v1, une bulle qui a du texte : lui poser le tag `grille-b`, et le tag
   `commun`.
2. *Atelier*, la case qui contient cette bulle : dans « Situation (scène) », taper
   `ambiance-b : tendue`.
3. *Exploration → 📖 Lexique* : ranger le tag `grille-b` ET la dimension `ambiance-b`
   dans « Étude B ». La valeur `tendue` suit sa dimension.

`grille-b` et `ambiance-b` sont alors LOCAUX à « Étude B », posés sur une région que
`lectrice` et `stagiaire` lisent par « Collection Test ». `commun` reste global.

**Une limite connue, qui n'est pas une case** : taper à la main le nom `grille-b` sous
`stagiaire` attache CE tag, qui disparaît aussitôt de son écran — le libellé est unique
dans toute l'instance. C'est une case ouverte d'AUTH-11, qui demande un changement de
schéma ; ne pas la jouer ici comme un échec.

### Ce que la lectrice ne voit pas

**Sous `lectrice`.**

- [ ] *Atelier*, la bulle du décor : ses tags montrent `commun` et pas `grille-b`
- [ ] *Atelier*, la case du décor : « Situation (scène) » ne montre pas `ambiance-b : tendue`
- [ ] *Recherche*, un mot de cette bulle : le résultat porte `commun` et pas `grille-b` ; le nuage de tags ne propose pas `grille-b`
- [ ] *Recherche*, l'adresse tapée à la main avec `?tags=grille-b` : aucun résultat, exactement comme avec un nom de tag qui n'existe pas
- [ ] *Exploration*, vue Croisement : la liste des axes ne propose pas `ambiance-b`, et l'axe « tag » ne fait pas de ligne `grille-b`
- [ ] *Exploration*, l'adresse tapée avec `?vue=croisement&axe_x=dim:<id>` — l'identifiant d'`ambiance-b`, relevé sous `proprio` — affiche la même erreur qu'avec un identifiant libre comme `dim:99999`, au nombre près, et aucun nom d'axe
- [ ] *Exploration → 📖 Lexique* : ni `grille-b`, ni `ambiance-b`, ni `tendue`

### L'écriture préserve ce qu'elle cache

**Sous `stagiaire`, puis sous `proprio`.** Le piège que le chantier a fermé : enregistrer
ce qu'on voit effaçait ce qu'on ne voyait pas.

- [ ] Sous `stagiaire`, la bulle du décor ne montre que `commun` ; lui ajouter une note, et enregistrer
- [ ] Sous `proprio`, la même bulle porte toujours `grille-b`, avec `commun` et la note du stagiaire
- [ ] Sous `stagiaire`, retirer `commun` : la bulle n'affiche plus aucun tag. Sous `proprio`, elle garde `grille-b` — vider ce qu'on voit n'a pas supprimé l'annotation
- [ ] Sous `stagiaire`, Ctrl+Z : `commun` revient. Sous `proprio`, `grille-b` est toujours là — l'annulation n'a pas effacé ce qui était caché

### Ce que le propriétaire voit, lui

**Sous `proprio`** — l'autre côté de chaque case, sans quoi les précédentes pourraient
passer sur un écran simplement cassé.

- [ ] La bulle montre `grille-b` et `commun`, la case `ambiance-b : tendue`
- [ ] *Recherche* avec `?tags=grille-b` trouve la bulle
- [ ] *Exploration*, Croisement : `ambiance-b` est proposé comme axe, et l'axe « tag » fait une ligne `grille-b`
