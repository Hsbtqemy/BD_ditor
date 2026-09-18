---
passe: Menu du compte, retour, modale d'album et annotation à deux onglets
chantier: —
duree: 15 min
derniere: —
---

# QA — ce que la journée du 2026-09-16 a changé à l'écran, et qu'aucune passe ne couvrait

Trois chantiers ont touché des écrans que les tests mesurent sans les REGARDER. `UX-14` a
rangé « Déconnexion » dans un menu ouvert par le nom du compte, et réduit « ← Retour » à son
icône. `AUTH-12` a borné la modale d'un nouvel album aux collections où l'on écrit, et fait
dire au message de création qui possède la collection. `CONC-3` a fait qu'un enregistrement
d'annotation n'efface plus ce qu'un autre écran a posé entre-temps. Les tests disent que les
éléments existent et que la base tient ; ils ne disent pas si l'on trouve le menu, si la
flèche se comprend, ni si le message se lit.

**Sur la pile locale**, `https://bd.127-0-0-1.sslip.io`, ouverte par `C:\temp\recette-chrome.cmd`
(Chrome sans le proxy du campus). **La pile doit servir `5caa373` ou un commit plus récent** :
sous `admin-bd`, *Administration → 🏷️ Version servie*. Plus ancienne, le menu du compte,
la modale bornée et l'annotation par différences n'y existent pas, et les cases échoueraient
sur un écran qui n'est pas le bon.

Le décor est celui des autres passes : `proprio` possède « Collection Test » et « Étude B »,
`lectrice` lit « Collection Test » par le groupe `annotateurs` et n'écrit nulle part,
`stagiaire` écrit dans « Collection Test ».

### Le menu du compte

**Sous `proprio`**, *Bibliothèque*, fenêtre large.

- [ ] En haut à droite, le nom du compte est suivi d'un « ▾ », et le mot « Déconnexion » n'apparaît nulle part dans la bande tant qu'on n'a pas cliqué sur le nom
- [ ] Cliquer sur le nom : un panneau s'ouvre juste en dessous, avec « Déconnexion » pour seule entrée ; cliquer ailleurs dans la page le referme
- [ ] Au clavier : `Tab` jusqu'au nom (son contour de focus se voit), `Entrée` ouvre le panneau, `Échap` le referme et le contour de focus est de nouveau sur le nom
- [ ] Ouvrir « Aa », puis cliquer sur le nom : le panneau « Affichage » se ferme quand celui du compte s'ouvre — les deux ne sont jamais ouverts ensemble
- [ ] Fenêtre réduite à sa largeur minimale (ou 375 px dans les outils de développement, mode appareil) : le nom et « Aa » restent dans la fenêtre sans que la page défile de côté, et le panneau du compte, ouvert, tient dans la fenêtre
- [ ] « Déconnexion » mène au portail de connexion (`auth.127-0-0-1.sslip.io`) ; se reconnecter sous `proprio` pour la suite

### « ← Retour » est une icône

**Sous `proprio`.**

- [ ] Depuis la *Bibliothèque*, cliquer « Atelier » dans la barre du haut : en tête de l'Atelier, une flèche « ← » apparaît SEULE, sans le mot « Retour », et la survoler affiche « Revenir d'où l'on vient »
- [ ] Cliquer sur la flèche ramène à la *Bibliothèque*
- [ ] Ouvrir l'Atelier directement par son adresse, dans un onglet neuf : aucune flèche n'apparaît, puisqu'il n'y a nulle part où revenir

### La modale d'album ne propose que là où l'on écrit

**Préalable de zone.** `stagiaire` n'a aujourd'hui qu'un accès, en écriture sur « Collection
Test » : il ne LIT aucune collection sans y écrire, et la première case ne prouverait rien.
Sous `proprio`, *Bibliothèque → 📚 Collections*, « Étude B » dépliée, partie *Qui entre* :
*Faire entrer* `stagiaire`, déclaré **compte**. Il entre en LECTURE, et l'on n'y touche
plus — c'est exactement l'accès que la zone demande. La dernière case de la zone le retire.

- [ ] Sous `stagiaire`, *Bibliothèque* : « Étude B » figure parmi les collections, puisqu'il la lit ; *+ Nouvel album* : la liste « Collection » propose « Collection Test » et PAS « Étude B ». Fermer sans créer
- [ ] Sous `lectrice`, *Bibliothèque → + Nouvel album*, AVANT de rien remplir : une note dit « Vous n'écrivez dans aucune collection : l'album ne pourra pas être créé. Demandez un accès en écriture au propriétaire d'une collection. » Fermer sans créer
- [ ] Sous `proprio`, *Bibliothèque → 📚 Collections*, créer « QA propriétaire » : le message dit « « QA propriétaire » créée — vous en êtes propriétaire. Pour y faire entrer quelqu'un : « Qui entre », dans la collection ouverte ci-dessous. » Supprimer ensuite « QA propriétaire »
- [ ] Sous `admin-bd`, même geste avec « QA administrateur » : le message dit qu'il l'administre comme administrateur de l'instance, SANS en être propriétaire, et l'invite à lui désigner un propriétaire dans « Qui entre », dans la collection ouverte ci-dessous — et non « vous en êtes propriétaire ». Supprimer ensuite « QA administrateur »
- [ ] Remettre en état : sous `proprio`, *Bibliothèque → 📚 Collections*, « Étude B » dépliée, *Qui entre* : « ✕ » sur la ligne de `stagiaire` ; le tableau d'« Étude B » ne montre plus que `proprio`, toutes ses cases cochées

### Deux onglets sur la même bulle

**Sous `proprio`**, l'Atelier sur *esther v1*, ouvert dans DEUX onglets. Choisir une bulle
dont le panneau *Annotation* est VIDE (ni note ni tag) et la sélectionner dans les deux
onglets, en mode *Annotation*. C'est la mesure 1 de `CONC-3` rejouée à la main : les deux
onglets sont ouverts avant le premier enregistrement, donc chacun a un état périmé.

- [ ] Onglet 2 : ajouter le tag `qa-onglet-2` et attendre « Enregistré ». Onglet 1, SANS recharger : taper « note onglet 1 » dans la note et attendre « Enregistré » — la puce `qa-onglet-2` apparaît alors dans l'onglet 1
- [ ] Recharger les deux onglets et resélectionner la bulle : elle porte la note « note onglet 1 » ET le tag `qa-onglet-2`. Avant `5caa373`, le tag disparaissait
- [ ] Remettre en état, dans un seul onglet : retirer la puce `qa-onglet-2`, vider la note, attendre « Enregistré » ; après rechargement, le panneau *Annotation* de la bulle est de nouveau vide
