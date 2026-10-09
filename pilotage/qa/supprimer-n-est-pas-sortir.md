---
passe: Supprimer n'est pas sortir, à l'écran
chantier: AUTH-10
duree: 30 min
derniere: —
---

# QA — un album partagé ne se supprime plus depuis une seule de ses collections

**Reportée le 2026-10-09, décision de Hugo** : cette passe n'a pas été jouée avant la fusion `dev` → `main`,
et la tranche 2 de `COL-3` la réécrira au lieu de la rejouer. Elle reste jouable telle quelle si un album partagé
entre deux collections apparaît en production d'ici là — cf. sa case dans `pilotage/AUTH-10.md`.

La suite verrouille le serveur : dix-neuf tests jouent la suppression sous plusieurs
identités et regardent ce que voient les AUTRES ensuite, un cliquet exige que toute route
qui détruit pose la garde, un test navigateur joue l'écran sous quatre identités. Ce qu'elle
ne voit pas, c'est **si l'écran se comprend** : une corbeille qui laisse place à un ✕, une
infobulle qui dit pourquoi, une confirmation qui annonce un aller simple, un album qui
quitte la liste. C'est ce que cette passe regarde.

**Elle se joue sur la pile locale complète**, à l'adresse `https://bd.127-0-0-1.sslip.io/`
(Chrome lancé avec `--no-proxy-server`, le certificat de Caddy accepté), derrière le proxy :
en mono-poste et sous un administrateur, tout album se supprime et rien de ce qui suit
n'apparaît. Une fenêtre de navigation PRIVÉE par identité.

| Identité | Ce qu'elle doit être pendant la passe |
|---|---|
| `admin-bd` | groupe `bd-admins` : monte le décor, puis constate |
| `stagiaire` | écrit dans « Incubateur QA », et ne VOIT pas l'album partagé avant la passe |
| `lectrice` | lit au moins un album, et n'écrit dans aucune de ses collections |

« L'album partagé » désigne ci-dessous un album de la base, au choix, qui a des planches et
que `stagiaire` **ne voit pas** au départ — la première case le vérifie. S'il le voyait par
une autre collection, la fin de la passe décrirait un autre écran : sorti de l'incubateur,
l'album resterait dans sa liste.

### Le décor

- [ ] Sous `stagiaire`, Bibliothèque : repérer un album ABSENT de sa liste, que `admin-bd` voit. C'est « l'album partagé ». Sous `admin-bd`, noter son titre, son nombre de planches et son nombre de régions
- [ ] Sous `admin-bd`, Bibliothèque → **📚 Collections** : créer « Incubateur QA ». Elle apparaît dans la liste, avec 0 album
- [ ] « Incubateur QA » dépliée, *Qui entre* : faire entrer le compte `stagiaire` (**+ Faire entrer**). Sa ligne apparaît au tableau, seule la case « lire » cochée
- [ ] Sur cette ligne, cocher la case des actes d'écriture — « annoter » et les trois qui lui sont liés, une seule case. Elle reste cochée après F5
- [ ] Ligne de l'album partagé → ✎ → bloc *Collections* → choisir « Incubateur QA » → **+ Ranger ici**. Le bloc montre l'album dans une collection de plus
- [ ] **+ Nouvel album**, titre « Seul QA », collection « Incubateur QA ». Sa ligne apparaît, et **📚 Collections** compte 2 albums dans « Incubateur QA »
- [ ] Toujours sous `admin-bd` : la ligne de l'album partagé porte la corbeille 🗑, et ses planches aussi (cliquer la ligne) — un administrateur écrit partout

### Sous `lectrice` — qui ne fait que lire ne se voit rien offrir

- [ ] Bibliothèque : sur un album qu'elle lit sans y écrire, la ligne porte ✎ et **ni 🗑 ni ✕**
- [ ] Cliquer cette ligne : ses planches s'affichent **sans** corbeille 🗑

### Sous `stagiaire` — ce qui n'est plus offert

- [ ] Bibliothèque : la ligne de « Seul QA » porte ✎ et 🗑 ; celle de l'album partagé porte ✎ et ✕, sans 🗑
- [ ] À 375 px de large : la ligne de l'album partagé n'est ni plus large ni plus haute que celle de « Seul QA » — ✕ tient la place de 🗑. Revenir ensuite à la largeur ordinaire
- [ ] Survoler le ✕ : l'infobulle dit que l'album est aussi rangé dans une collection où l'on n'écrit pas, et qu'on peut le sortir de la sienne. Elle ne NOMME aucune collection
- [ ] Cliquer la ligne de l'album partagé : ses planches s'affichent avec leur rôle, leur verrou et ↗, **sans** corbeille 🗑
- [ ] Sur une de ces planches, poser le verrou 🔒 puis le retirer : les deux aboutissent — ce qui n'est pas détruire reste permis
- [ ] Le nom de l'autre collection de l'album partagé n'apparaît nulle part sur la page : ni dans la liste, ni dans **📚 Collections**

### Sous `stagiaire` — le geste qui reste

- [ ] Cliquer le ✕ de la ligne : la fiche de l'album s'ouvre ; sous *Collections*, « Incubateur QA » est la seule collection listée, une phrase redit pourquoi l'album ne se supprime pas d'ici, et le focus est sur le ✕ de « Incubateur QA » (son anneau se voit)
- [ ] **Annuler**, puis rouvrir la fiche par ✎ : la phrase n'y est plus
- [ ] Rouvrir par le ✕ de la ligne, actionner le ✕ de « Incubateur QA » : une confirmation demande si l'on veut sortir l'album, et prévient qu'on ne le verra plus et qu'on ne pourra pas l'y ranger de nouveau soi-même. Elle ne nomme aucune autre collection
- [ ] Refuser la confirmation : rien ne bouge, la fiche reste ouverte, la ligne est toujours dans la liste
- [ ] Actionner de nouveau le ✕ et accepter : la fiche se ferme, « Album sorti de « Incubateur QA ». » s'affiche, la ligne de l'album a quitté la liste, celle de « Seul QA » y est toujours
- [ ] **📚 Collections** : « Incubateur QA » compte 1 album

### L'album a survécu

- [ ] Sous `admin-bd` : l'album partagé est dans la liste, avec les nombres de planches et de régions notés au départ
- [ ] Sa fiche (✎) ne le montre plus dans « Incubateur QA »

### Le même geste, quand on continue de lire l'album

Sortir un album de la seule collection où l'on y ÉCRIVAIT est un aller simple même si on le
lit encore par une autre : on y perd l'écriture, pas la vue, et la confirmation doit dire
lequel des deux. Aucun compte de la recette n'est dans ce cas au départ ; la zone le monte.

- [ ] Sous `admin-bd` : ranger de nouveau l'album partagé dans « Incubateur QA » (✎ → *Collections* → **+ Ranger ici**), puis, dans la collection d'ORIGINE de l'album, *Qui entre* : faire entrer le compte `stagiaire`, « lire » seul
- [ ] Sous `stagiaire`, Bibliothèque rechargée : la ligne de l'album partagé porte ✎ et ✕. Cliquer le ✕ : la fiche liste DEUX collections, et le focus est sur le ✕ de « Incubateur QA », pas sur celui de l'autre
- [ ] Actionner ce ✕ : la confirmation dit qu'on continuera de lire l'album mais qu'on n'y écrira plus, et qu'on ne pourra pas l'y ranger de nouveau soi-même. Elle ne dit PAS « vous ne le verrez plus »
- [ ] Accepter : la fiche reste ouverte et ne liste plus que la collection d'origine. La fermer : la ligne de l'album est toujours dans la liste, avec ✎ et **ni 🗑 ni ✕**
- [ ] Sous `admin-bd` : retirer l'accès de `stagiaire` à la collection d'origine. Sa ligne quitte le tableau

### Ce qui n'a pas bougé

- [ ] Sous `stagiaire` : 🗑 sur « Seul QA », confirmer. L'album disparaît — un album d'une seule collection se supprime comme avant
- [ ] Sous `admin-bd` : supprimer « Incubateur QA », désormais vide. La base est rendue comme on l'a trouvée
