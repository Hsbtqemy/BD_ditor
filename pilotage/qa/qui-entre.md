---
passe: Qui entre
chantier: AUTH-12
duree: 30 min
derniere: 2026-09-18
---

# QA — régler qui entre depuis la collection, en actes

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, reconstruite sur
`6ea6b60` ou après, avec l'annuaire réellement lu (et non sa doublure). Les mots de passe
sont dans `C:\temp\bd-recette\comptes.txt`, hors dépôt. Une fenêtre privée par identité.

**Ce que la passe éprouve.** Les accès d'une collection se règlent en tête de CETTE collection,
dans la Bibliothèque, en ACTES et non en niveaux ; l'Administration ne les montre plus qu'en
lecture et y mène. Les gestes joués sont ceux que la maquette validée faisait jouer au
propriétaire : faire entrer un cours, changer ses actes, retirer un accès.

**La passe ne touche PAS « Collection Test »**, qui porte le décor d'autres passes (*Compte
collectif*, *Les collections dans la Bibliothèque*). Elle crée sa propre collection, « Essai qui
entre », et la supprime à la fin. Ne pas sauter la remise en état.

**Ce que la passe ne joue pas, et où c'est éprouvé.** L'annuaire en panne : l'arrêter toucherait
la pile, et c'est joué par `tests/test_e2e_qui_entre.py`. L'absence des mots « principal »,
« genre » et « utilisateur » à l'écran : mesurée par le même fichier.

### Le propriétaire crée, et « Qui entre » vient en premier
- [x] Sous `proprio`, *Bibliothèque → 📚 Collections*, créer « Essai qui entre » : le message sous le champ dit « vous en êtes propriétaire » et renvoie à « Qui entre », dans la collection ouverte ci-dessous
- [x] La collection s'ouvre : sa première partie s'intitule « Qui entre », avant les champs *Description* ; son résumé porte la pastille « propriétaire »
- [x] Le tableau a une colonne par acte — lire, annoter, organiser les albums, gérer le vocabulaire, lancer la reconnaissance automatique, décider qui entre —, puis « exporter », « Depuis le » et « Signal » ; `proprio` y est seul, avec toutes ses cases cochées
- [x] Sur la ligne de `proprio`, la case « exporter » est cochée, grisée, et suivie de « (d'office) »

### Faire entrer un cours
- [x] La liste *Faire entrer* commence par « Choisir… », puis « Groupes de l'annuaire », puis « Un compte, ou un groupe absent de la liste… ». Elle ne propose aucun compte, ni `bd-admins`, ni aucun groupe `lldap_…`
- [x] Sans rien choisir, « + Faire entrer » : un refus rouge s'affiche sous la ligne d'ajout, et le tableau ne change pas
- [x] Choisir `annotateurs`, « + Faire entrer » : le message dit « Le groupe annotateurs entre dans « Essai qui entre », en lecture. Cochez les autres actes. », et une ligne `annotateurs` apparaît, seule la case « lire » cochée
- [x] Sur cette ligne, les quatre actes d'écriture n'ont qu'UNE case, traversée d'une barre. La cocher : elle reste cochée une fois le tableau redessiné, et après F5
- [x] Choisir à nouveau `annotateurs`, « + Faire entrer » : le refus dit qu'il « entre déjà », et sa case d'écriture reste cochée — rien n'a été rétrogradé

### Un nom tapé
- [x] Choisir « Un compte, ou un groupe absent de la liste… », taper `cours-qui-n-existe-pas`, laisser « Compte ou groupe ? », « + Faire entrer » : le refus demande de dire si c'est un compte ou un groupe, et le nom tapé reste dans le champ
- [x] Choisir « Groupe », « + Faire entrer » : le message, en ambre, dit que le groupe « n'est pas dans l'annuaire : l'accès est accordé, en lecture, mais n'ouvrira rien tant que ce nom n'y existe pas », et sa ligne porte « inconnu de l'annuaire » dans *Signal*

### Retirer, et ce qu'on ne peut pas retirer
- [x] Sur la ligne de `proprio`, décocher « décider qui entre » : un refus rouge nomme le dernier propriétaire, et la case revient cochée
- [x] « ✕ » sur `cours-qui-n-existe-pas` : la ligne disparaît, et le focus clavier est sur le titre « Qui entre »

### Depuis l'Administration
- [x] Sous `admin-bd`, *Administration* : aucun bloc « 👥 Accès aux collections » ; l'en-tête de la page dit que qui entre dans une collection se règle dans la Bibliothèque
- [x] *👥 Comptes et groupes*, axe *Collections*, « Essai qui entre » : *Qui entre* liste `proprio` et `annotateurs` avec leurs actes en toutes lettres (« tous les actes, dont décider qui entre » ; « lire, annoter · organiser les albums · … »), sans aucune case à cocher
- [x] « Régler qui entre » : la Bibliothèque s'ouvre sur « Essai qui entre » dépliée, le focus sur « Qui entre », et le résumé porte la pastille « administrateur »
- [x] Revenir à l'Administration, axe *Groupes*, `annotateurs`, *Ouvrir une collection à ce groupe* : choisir « Essai qui entre », « Régler qui entre… » : la Bibliothèque s'ouvre sur la collection, `annotateurs` déjà choisi dans *Faire entrer*

### Qui participe ne voit pas qui entre
- [x] Sous `lectrice`, *Bibliothèque*, déplier « Collection Test » : aucune partie « Qui entre », la phrase « Seul un propriétaire de la collection voit et règle qui y entre », et la note qui nomme les administrateurs de l'instance

### Largeur, clavier, lecteur d'écran, thème
- [x] Sous `proprio`, outils de développement en mode appareil à 375 px, « Essai qui entre » dépliée : une CARTE par accès, avec « lire », puis les quatre actes d'écriture sur une seule case, puis « décider qui entre » et « exporter » ; rien ne dépasse à droite
- [x] Au clavier seul, à pleine largeur : Tab jusqu'à la case d'écriture d'`annotateurs`, Espace la décoche ; après le rechargement, le focus est encore sur cette case
- [x] Sous NVDA, focus sur la case d'écriture d'`annotateurs` : NVDA annonce le groupe et les quatre actes (« annoter, organiser les albums, gérer le vocabulaire, lancer la reconnaissance automatique »), et l'état de la case
- [x] Thème clair (🌙 → ☀) : la marque ambre « inconnu de l'annuaire » (la rejouer si besoin) et un refus rouge restent lisibles

### Remise en état
- [x] **Sous `proprio`**, « Essai qui entre » dépliée, *Supprimer la collection* : elle disparaît de la liste ; « Collection Test » garde ses accès d'avant la passe
