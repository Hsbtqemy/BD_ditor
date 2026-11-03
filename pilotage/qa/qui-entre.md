---
passe: Qui entre
chantier: UX-20
duree: 35 min
derniere: 2026-09-18
---

# QA — régler qui entre dans une collection : les membres du projet, en actes

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, reconstruite sur
`829fbb2` ou après, avec l'annuaire réellement lu (et non sa doublure). Les mots de passe
sont dans `C:\temp\bd-recette\comptes.txt`, hors dépôt. Une fenêtre privée par identité.

**Réécrite le 2026-11-03** (`4460a8a`, COL-3, tranche 3c, F2) : toutes les cases sont neuves
et décochées. La passe du 2026-09-18 jouait la saisie libre (« Un compte, ou un groupe absent
de la liste… », « Compte ou groupe ? ») et une Bibliothèque d'avant ses onglets.

**Ce que la passe éprouve.** Les accès d'une collection se règlent dans l'onglet « Qui entre »
de sa fiche, dans la Bibliothèque, en ACTES et non en niveaux, et le même panneau est monté
dans l'Administration. **On n'entre dans une collection que si l'on est du projet** : la
ligne d'ajout ne propose que les membres du projet qui n'entrent pas encore, et dit qui fait
entrer quelqu'un d'autre.

**Le décor attendu**, celui de l'état `base` restauré : dans « Projet principal », `proprio`
est responsable ; `arrivant` et `stagiaire` (comptes), `annotateurs` et `etudiants` (groupes)
en sont membres. `arrivant` est propriétaire de « Carnet d'arrivant ».

**La passe ne touche PAS « Collection Test »**, qui porte le décor d'autres passes. Elle crée
sa propre collection, « Essai membres », et la supprime à la fin. Ne pas sauter la remise en
état : elle fait aussi sortir du projet le groupe que la passe y a fait entrer.

**Ce que la passe ne joue pas, et où c'est éprouvé.** L'annuaire en panne : l'arrêter
toucherait la pile, et c'est joué par `tests/test_e2e_qui_entre.py`. L'absence des mots
« principal », « genre » et « utilisateur » à l'écran : mesurée par le même fichier. « Qui
entre » d'un bac à sable : `tests/test_e2e_qui_entre.py`.

### Le responsable crée, et « Qui entre » vient en premier
- [ ] Sous `proprio`, *Bibliothèque*, « + Créer une collection » sous la liste des collections, nommer « Essai membres » : le message dit « « Essai membres » créée — vous en êtes propriétaire. Pour y faire entrer quelqu'un : « Qui entre », dans sa fiche. »
- [ ] La fiche d'« Essai membres » s'ouvre sur l'onglet « Qui entre », sélectionné parmi *Albums · Qui entre · Description · Diffusion et dépôt* ; dans le rail, la collection porte « propriétaire »
- [ ] Le tableau a une colonne par acte — lire, annoter, organiser les albums, gérer le vocabulaire, lancer la reconnaissance automatique, décider qui entre —, puis « exporter », « Depuis le » et « Signal » ; `proprio` y est seul, avec toutes ses cases cochées
- [ ] Sur la ligne de `proprio`, la case « exporter » est cochée, grisée, et suivie de « (d'office) »

### La liste ne propose que les membres du projet
- [ ] La liste *Faire entrer* commence par « Choisir un membre du projet… », puis un groupe *Comptes* (`arrivant`, `stagiaire`) et un groupe *Groupes* (`annotateurs`, `etudiants`). Elle ne propose ni `proprio` (il entre déjà), ni `bd-admins`, ni aucun groupe `lldap_…`, ni « Un compte, ou un groupe absent de la liste… »
- [ ] Sous la liste : « Quelqu'un manque ? Faites-le d'abord entrer dans le projet ↗ », un lien
- [ ] Sans rien choisir, « + Faire entrer » : le refus rouge « Choisissez un membre du projet dans la liste. » s'affiche sous la ligne d'ajout, et le tableau ne change pas
- [ ] Choisir `annotateurs`, « + Faire entrer » : le message dit « Le groupe annotateurs entre dans « Essai membres », en lecture. Cochez les autres actes. », et une ligne `annotateurs` apparaît, seule la case « lire » cochée
- [ ] `annotateurs` a quitté la liste *Faire entrer* : il ne s'y propose plus, ce qui empêche de le faire entrer une seconde fois (et de le rétrograder en lecture)
- [ ] Sur la ligne d'`annotateurs`, les quatre actes d'écriture n'ont qu'UNE case, traversée d'une barre. La cocher : elle reste cochée une fois le tableau redessiné, et après F5

### Quelqu'un manque : le faire entrer dans le projet d'abord
- [ ] « Faites-le d'abord entrer dans le projet ↗ » : l'Administration s'ouvre sur la vue *Projets*, fiche de « Projet principal », et sa partie *Qui y entre*
- [ ] Dans *Qui y entre*, *Faire entrer* → « Un compte, ou un groupe absent de la liste… », taper `cours-qui-n-existe-pas`, choisir « Groupe », « + Faire entrer » : une ligne `cours-qui-n-existe-pas`, rôle *membre*, marquée « inconnu de l'annuaire »
- [ ] Revenir à l'onglet de la Bibliothèque, F5 : `cours-qui-n-existe-pas` est proposé sous *Groupes*. Le choisir, « + Faire entrer » : le message, en ambre, dit que le groupe « n'est pas dans l'annuaire : l'accès est accordé, en lecture, mais n'ouvrira rien tant que ce nom n'y existe pas », et sa ligne porte « inconnu de l'annuaire » dans *Signal*

### Retirer, et ce qu'on ne peut pas retirer
- [ ] Sur la ligne de `proprio`, décocher « décider qui entre » : un refus rouge nomme le dernier propriétaire, et la case revient cochée
- [ ] « ✕ » sur `cours-qui-n-existe-pas` : la ligne disparaît, le focus clavier est sur le titre « Qui entre », et `cours-qui-n-existe-pas` revient dans la liste *Faire entrer*

### Un membre sorti du projet entre la liste et le geste
- [ ] Sans recharger la Bibliothèque, dans l'onglet de l'Administration, *Qui y entre* de « Projet principal » : « ✕ » sur `cours-qui-n-existe-pas` — il sort du projet
- [ ] Revenir à la Bibliothèque SANS recharger : `cours-qui-n-existe-pas` est encore dans la liste. Le choisir, « + Faire entrer » : un refus rouge dit « Le groupe « cours-qui-n-existe-pas » n'est pas du projet « Projet principal » : faites-le entrer dans le projet d'abord… », et aucune ligne n'apparaît
- [ ] F5 : `cours-qui-n-existe-pas` n'est plus proposé

### Une adresse qui présélectionne un groupe
- [ ] Ouvrir `/corpus?collection=<id d'« Essai membres »>&groupe=etudiants` (l'identifiant se lit dans l'adresse quand la fiche est ouverte) : `etudiants` est déjà choisi dans *Faire entrer*, et rien n'est accordé tant qu'on n'a pas cliqué « + Faire entrer »
- [ ] Même adresse avec `&groupe=cours-qui-n-existe-pas` : au-dessus de la ligne d'ajout, « Le groupe cours-qui-n-existe-pas n'est pas du projet « Projet principal » : faites-le d'abord entrer dans le projet. », et *Faire entrer* reste sur « Choisir un membre du projet… »

### Qui n'est pas responsable : « Quelqu'un manque ? » nomme le responsable
- [ ] Sous `arrivant`, *Bibliothèque*, « Carnet d'arrivant », onglet « Qui entre » : sous la liste, « Quelqu'un manque ? » suivi de `proprio` (son nom lisible s'il en a un) et de « responsable du projet, le fait entrer. », sans lien

### Depuis l'Administration
- [ ] Sous `admin-bd`, *Administration* → *👥 Comptes et groupes* : l'en-tête dit que qui entre dans une collection « se règle aussi ici », dans sa fiche — axe *Collections*
- [ ] Axe *Collections*, « Essai membres » : *Qui entre* y est le MÊME panneau que dans la Bibliothèque — `proprio` et `annotateurs`, chacun avec ses cases cochées selon ses actes, la liste *Faire entrer* des membres du projet, « Quelqu'un manque ? » avec son lien, et un ✕ au bout de chaque ligne
- [ ] Sous le panneau, « Décrire dans la Bibliothèque ↗ » : la Bibliothèque s'ouvre sur la fiche d'« Essai membres », et la collection porte « administrateur » dans le rail
- [ ] Revenir à l'Administration, axe *Groupes*, `etudiants`, *Ouvrir une collection à ce groupe* : choisir « Essai membres », « Régler qui entre… » : la FICHE de la collection s'ouvre, dans l'Administration, `etudiants` déjà choisi dans *Faire entrer*, et rien n'est accordé tant qu'on n'a pas cliqué « + Faire entrer »

### Qui participe ne voit pas qui entre
- [ ] Sous `lectrice`, *Bibliothèque*, « Collection Test », onglet « Qui entre » : aucun tableau, la phrase « Seul un propriétaire de la collection voit et règle qui y entre. », et la note qui nomme les administrateurs de l'instance

### Largeur, clavier, lecteur d'écran, thème
- [ ] Sous `proprio`, outils de développement en mode appareil à 375 px, fiche d'« Essai membres » sur « Qui entre » : une CARTE par accès, avec « lire », puis les quatre actes d'écriture sur une seule case, puis « décider qui entre » et « exporter » ; la liste *Faire entrer* et « Quelqu'un manque ? » passent à la ligne sans rien faire dépasser à droite
- [ ] Au clavier seul, à pleine largeur : Tab jusqu'à la case d'écriture d'`annotateurs`, Espace la décoche ; après le rechargement, le focus est encore sur cette case
- [ ] Sous NVDA, focus sur la case d'écriture d'`annotateurs` : NVDA annonce le groupe et les quatre actes (« annoter, organiser les albums, gérer le vocabulaire, lancer la reconnaissance automatique »), et l'état de la case
- [ ] Thème clair (🌙 → ☀) : l'avis « … n'est pas du projet » (rejouer l'adresse `&groupe=cours-qui-n-existe-pas`) et un refus rouge restent lisibles

### Remise en état
- [ ] **Sous `proprio`**, fiche d'« Essai membres », onglet *Description*, « Supprimer la collection… » en bas : elle disparaît de la liste ; « Collection Test » garde ses accès d'avant la passe
- [ ] *Administration*, *Projets*, « Projet principal », *Qui y entre* : `cours-qui-n-existe-pas` n'y est plus (sinon, « ✕ » sur sa ligne)
