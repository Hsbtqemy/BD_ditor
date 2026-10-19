---
passe: La Bibliothèque en calque
chantier: UX-18
duree: 60 min
derniere: —
---

# QA — la Bibliothèque en liste et fiche : la collection en calque, la fiche à quatre onglets, la fiche d'un album

**Écrite le 2026-10-18 sur `53a4b6a`, non jouée.** Elle porte sur `555de64` (la Bibliothèque
en liste et fiche, la collection en calque) et `58b2d4f` (valider une planche est un bouton qui
porte son état), et sert la case d'`UX-18` « Les passes de QA disent le nouvel écran ».

**Ce que les tests couvrent déjà — ne pas le refaire ici** : la logique du calque, du tri, de
l'adresse et des droits d'un album (tables de vérité Node, `tests/js/bibliotheque.test.js`) ;
les sélecteurs épinglés ; l'audit axe de la Bibliothèque dans les deux thèmes ; le reflow à 320
et 768 px. **Ce qui se regarde ici** : si l'on comprend ce que fait une case et ce que fait un
nom, si l'on se repère d'une fiche à l'autre, et si ce que l'écran dit est vrai sous chaque
identité.

**Ce que la passe ne juge pas** : les gestes de la tranche 3a de `COL-3` — prendre du fonds,
prendre dans le projet, les demandes reçues ⚑, la collection de base —, qui ont leur passe,
`prendre-un-document` ; les deux réponses à « Supprimer… », qui ont la leur,
`supprimer-n-est-pas-sortir` ; et le lot qui ne dit pas encore sur quoi il travaille (case
ouverte d'`UX-18`, serveur à écrire).

Les zones se jouent DANS L'ORDRE : chacune s'appuie sur ce que la précédente a laissé. La
dernière rend la recette.

## Reste

### Le décor — `C:\temp\bd-recette\etat-de-base.ps1`, puis comptes `admin-bd` et `proprio`

- [x] `C:\temp\bd-recette\etat-de-base.ps1 restaurer` répond « bd-app : healthy » (ou « running ») — la passe crée des albums et une collection, change des validations : la dernière zone rend la recette
- [x] Sous `admin-bd` (une fenêtre privée par compte, pour toute la passe), `https://bd.127-0-0-1.sslip.io/administration?vue=instance` : « 🏷️ Version servie » affiche `53a4b6a` ou plus récent — sur un serveur plus ancien, la Bibliothèque n'est pas en calque et rien de ce qui suit ne mesure
- [x] Sous `proprio`, Bibliothèque, la fiche du projet à droite (rien de choisi) : **+ Nouvel album** ; *Collection* propose « — choisir — » présélectionné, « Collection Test » et « Étude B » ; titre « Calque A QA », choisir « Collection Test », *Enregistrer* : « Album enregistré » s'affiche et « Calque A QA » paraît dans la liste des albums
- [x] Sous `proprio`, Bibliothèque : cliquer le NOM « Étude B » dans le bloc « Collections » (sa fiche s'ouvre à droite), puis **+ Nouvel album** : *Collection* est déjà sur « Étude B » ; titre « Calque B QA », *Enregistrer* — la collection ouverte est présélectionnée
- [x] Sous `proprio`, Atelier : choisir « Calque A QA » dans la liste *Album* (l'Atelier ouvre le premier de la liste, pas celui qu'on vient de créer), puis *⇅ Import / Export* → *⤓ Importer des images…* → DEUX images JPEG ou PNG du poste : deux planches paraissent dans la barre latérale
- [x] Sous `proprio`, Bibliothèque, nom « Collection Test » → onglet *Qui entre* : sur la ligne de `stagiaire`, la case « exporter » est DÉCOCHÉE (la décocher sinon, et constater qu'elle le reste après F5) — une zone plus bas a besoin d'une annotatrice sans le droit d'exporter

### La liste — compte `proprio`, Bibliothèque, rien de choisi

- [x] Au-dessus du cadre, « Dans le projet « Projet principal » » ; à gauche, le titre « Collections · 2 », puis « Collection Test » et « Étude B », chacune avec une case à cocher, son nom, la pastille « propriétaire » et un nombre d'albums (« Collection Test » 2, « Étude B » 2)
- [x] Sous le bloc, le titre « Albums », un champ « Titre, série, auteur… », et trois lignes : « Calque A QA » (« 2 pl. », « Collection Test »), « Calque B QA » (« 0 pl. », « Étude B ») et « esther v1 » (« Collection Test · Étude B ») ; en tête de la liste, « 3 albums que vous lisez »
- [x] Taper `calque` dans le champ : deux lignes restent, et le compte dit « 2 albums sur 3 que vous lisez » ; taper `zzz` : « Aucun album ne répond. » ; vider le champ
- [x] **+ Créer une collection** (en tête de la liste) : un champ « Nom de la collection » et *Créer* paraissent sous le bouton ; *Créer* sans nom affiche, juste sous le champ, « Donnez un nom à la collection. »
- [x] Nom « Zèbre QA », *Créer* : sous le champ, « « Zèbre QA » créée — vous en êtes propriétaire. Pour y faire entrer quelqu'un : « Qui entre », dans sa fiche. » ; sa fiche s'ouvre à droite sur l'onglet *Qui entre*, et le bloc dit « Collections · 3 »
- [x] Bloc « Collections », *Trier* : « A → Z » (enfoncé) range « Collection Test », « Étude B », « Zèbre QA » ; « Récentes d'abord » met « Zèbre QA » en tête ; revenir à « A → Z »

### Le calque : la case filtre, le nom ouvre — compte `proprio`, Bibliothèque

- [x] Cocher la CASE de « Collection Test » : la liste des albums ne garde que « Calque A QA » et « esther v1 » (« 2 albums sur 3 que vous lisez »), le nom « Collection Test » ressort en bleu sur leurs lignes, et la fiche de « Collection Test » s'ouvre à droite sur l'onglet *Albums*
- [x] Le lien « Tout ce que vous lisez » a paru à côté du titre « Collections » ; le cliquer : la case se décoche, les trois albums reviennent, la fiche du projet revient à droite, et le lien disparaît
- [x] Cocher « Collection Test » puis « Étude B » : à droite, « Comparer 2 collections » — un tableau à deux colonnes, *Albums* 2 sous chacune, *Planches*, *Validées*, *Régime* « sans régime » ; puis *Recoupement* : « seulement Collection Test : 1 », « dans les deux : 1 », « seulement Étude B : 1 »
- [x] Sous les collections, *Montrer* « Dans l'une » (enfoncé) / « Dans toutes » a paru ; « Dans toutes » : la liste ne garde que « esther v1 » (« 1 album sur 3 que vous lisez ») ; « Dans l'une » : les trois reviennent
- [x] Dans la comparaison, le bouton « Ne montrer que le seul en commun » fait le même geste que « Dans toutes »
- [x] « Tout ce que vous lisez », puis cliquer le NOM « Étude B » (et non sa case) : sa fiche s'ouvre sur l'onglet *Qui entre*, aucune case n'est cochée, et la liste montre toujours les trois albums

### La fiche du projet — comptes `proprio` puis `admin-bd`, Bibliothèque, rien de choisi

- [x] Sous `proprio` : le titre « Projet principal », sous lui « 3 albums que vous lisez » et « 3 collections que vous lisez » ; une barre d'avancement « Tout ce que vous lisez · 3 album(s) · … planche(s) · ✔ … validée(s) » ; AUCUN bouton « + Prendre du fonds… » (`proprio` n'est pas responsable de ce projet)
- [x] Sous `proprio`, partie « Les collections, posées sur ce que vous lisez » : une ligne par collection, son nom en lien et « k / 3 » avec une barre (« Collection Test » 2 / 3, « Étude B » 2 / 3, « Zèbre QA » 0 / 3), puis « 1 album sur plusieurs collections. Cochez une collection pour filtrer les albums ; son nom ouvre sa fiche. » ; le lien « Étude B » ouvre sa fiche sur l'onglet *Albums*
- [x] Sous `admin-bd` : la première collection du bloc est « Projet principal », marquée « base » (la collection de base que la v31 a donnée au projet de repli) ; chacune porte la pastille « administrateur » ; le compte des albums dit « N albums », sans « que vous lisez » ; la partie s'intitule « Les collections, posées sur le corpus » ; une case cochée fait paraître « Tout le projet », et non « Tout ce que vous lisez »

### La fiche d'une collection : vos droits en actes, quatre onglets — compte `proprio`, Bibliothèque, « Collection Test »

- [x] Cliquer le nom « Collection Test » : la fiche dit « Collection Test », sous lui « 2 albums », « propriétaire », la puce « sans régime », puis une ligne « ✓ lire », « ✓ annoter et organiser », « ✓ exporter », « ✓ décider qui entre », et quatre onglets *Albums* · *Qui entre* · *Description* · *Diffusion et dépôt*, *Qui entre* sélectionné
- [x] Au clavier, le focus sur l'onglet *Qui entre* : → sélectionne *Description* et montre son panneau ; Fin sélectionne *Diffusion et dépôt* ; Début sélectionne *Albums* ; une seule tabulation suffit pour passer des onglets au panneau
- [x] Onglet *Albums* : un tableau *Titre* · *Planches* · *Validées* · *Aussi dans* ; « Calque A QA » (2, « 0/2 », un tiret sous *Aussi dans*) et « esther v1 » (« Étude B » sous *Aussi dans*) ; chaque ligne porte ✎ et « Supprimer… » ; au-dessus, « Cochez des albums pour lancer un lot de segmentation, de bulles ou d'OCR. »
- [x] Cocher la case de « Calque A QA » : la phrase laisse place à « 1 album sélectionné », trois cases *Segmenter* · *Bulles* · *OCR*, « ▶ Lancer » éteint tant qu'aucune passe n'est cochée, et « Tout désélectionner » — qui, cliqué, ramène la phrase ; NE PAS lancer
- [x] Onglet *Description* : « Nom », « Description », « Période », « Référent » en lecture, et un bouton *Modifier* ; *Modifier* ouvre le formulaire (groupes « Description » et « Référent — à qui s'adresser »), le premier champ a le focus ; *Enregistrer* sans rien changer affiche « Rien n'a changé. »
- [x] Ajouter un mot à la description, *Enregistrer* : « « Collection Test » enregistrée. » s'affiche dans l'onglet, le formulaire se referme sur la lecture, qui montre le mot ajouté ; *Modifier*, retirer le mot, *Enregistrer* — le décor est rendu
- [x] En bas de *Description*, à part, sous un filet, « Supprimer la collection… » — il n'est pas collé à *Enregistrer* (formulaire ouvert ou non). NE PAS cliquer ici
- [x] Onglet *Diffusion et dépôt* : « Régime de diffusion » « sans régime », « Fin d'embargo », « Licence », « Base légale » en lecture, la note « Le régime décide de ce qui SORT de l'instance… », *Modifier*, puis « Export de dépôt » et ses boutons (*JSON*, *CSV*, *XLSX*, *Télécharger*) ; *Modifier* ouvre le groupe « Diffusion — ce qui sort de l'instance » et *Annuler* le referme sans rien enregistrer
- [x] Fiche de « Zèbre QA », onglet *Description*, « Supprimer la collection… » : la confirmation dit « Supprimer « Zèbre QA » ? Ses albums ne sont pas supprimés : ils sortent simplement de cette collection. » ; l'accepter : la fiche du projet revient avec « « Zèbre QA » supprimée. », et le bloc dit « Collections · 2 »

### Aucun onglet n'est gardé — comptes `stagiaire` et `lectrice`, Bibliothèque, « Collection Test »

- [x] Sous `stagiaire`, fiche de « Collection Test » : « ✓ lire », « ✓ annoter et organiser », puis « exporter » et « décider qui entre » BARRÉS et précédés d'un tiret — l'absence se lit sans la couleur
- [x] Sous `stagiaire`, onglet *Diffusion et dépôt* : il s'ouvre, le régime se lit, et sous « Export de dépôt », « Exporter : droit manquant. » puis « Exporter cette collection demande le droit d'exporter, que son propriétaire accorde accès par accès : la lire n'y suffit pas. » ; aucun bouton *Modifier*
- [x] Sous `stagiaire`, onglet *Description* : la lecture, et à la place de *Modifier* « Seul un propriétaire de la collection modifie sa description, son régime de diffusion et son référent. » ; pas de « Supprimer la collection… »
- [x] Sous `stagiaire`, onglet *Qui entre* : il s'ouvre, et dit « Seul un propriétaire de la collection voit et règle qui y entre. », suivi de la note « Les administrateurs de l'instance (…) lisent et écrivent toute collection, sans figurer dans aucune liste d'accès. … » — pas de tableau, pas de « Faire entrer »
- [x] Sous `lectrice`, onglet *Albums* : les lignes n'ont ni ✎ ni « Supprimer… » ; « ✓ lire », et « annoter et organiser » barré

### La fiche d'un album, à la place de la collection — compte `proprio`, Bibliothèque

- [x] Fiche de « Collection Test », onglet *Albums*, cliquer le titre « Calque A QA » : sa fiche REMPLACE celle de la collection, avec en tête « ← Collection Test » ; dans la liste de gauche, la ligne « Calque A QA » est marquée comme courante
- [x] En tête de la fiche, trois boutons : « ✎ Modifier l'album », « ✔ Tout valider », « Supprimer… » ; dessous, *Sur les collections* : « Collection Test » cochée, « Étude B » non cochée, toutes deux actives
- [x] Cocher « Étude B » : la case reste cochée, et sous elles « Fait : « Calque A QA » est aussi rangé dans « Étude B ». Le travail est partagé. » ; la ligne de l'album dit maintenant « Collection Test · Étude B »
- [x] Décocher « Étude B » : AUCUNE confirmation (`proprio` tient les deux collections), et « « Calque A QA » n'est plus dans « Étude B ». Le travail continue ailleurs. » ; la recocher, pour le décor : « Fait : … » de nouveau
- [x] « ← Collection Test » ramène la fiche de la collection sur l'onglet *Albums* ; la ligne de « Calque A QA » dit « Étude B » sous *Aussi dans*

### Les planches : les gestes après le nom, la validation qui porte son état — compte `proprio`, fiche de « Calque A QA »

- [x] Le tableau des planches : sur chaque ligne, juste après le numéro de planche, les gestes 🏷 · 🔓 · ↗ · 🗑, dans cet ordre — la corbeille n'est pas la dernière colonne, et elle se voit sans faire défiler le tableau de côté
- [x] La corbeille de chaque planche est ACTIVE (`proprio` a importé l'album, personne d'autre n'y a travaillé) : pleine, sans contour pointillé, et son fond passe au rouge au survol. NE PAS cliquer
- [x] Colonne *Validée* : un bouton ✔ GRIS par planche ; le survoler dit « Marquer comme validée » ; le cliquer : il devient VERT, avec une bordure et un fond teintés ; le survoler dit maintenant « Validée le … — cliquer pour retirer la validation »
- [x] Recliquer ce ✔ vert : il redevient gris — le même bouton dans les deux sens, sans ↺ ni badge ✔ à côté
- [x] « ✔ Tout valider » : une confirmation « Valider 2 planche(s) de cet album ? » ; l'accepter : « 2 planche(s) validée(s). » sous les boutons de tête, et les deux ✔ verts ; recliquer « ✔ Tout valider » : « Toutes les planches sont déjà validées. », sans confirmation
- [x] « ← Collection Test » : onglet *Albums*, la ligne de « Calque A QA » dit « 2/2 » en vert sous *Validées*
- [x] Rouvrir « Calque A QA », cocher la case de la première planche : « 1 planche sélectionnée », les passes, « ▶ Lancer » et « Tout désélectionner » paraissent au-dessus du tableau ; ouvrir ensuite « esther v1 » dans la liste de gauche : sa fiche dit « La sélection de 1 planche de « Calque A QA » a été vidée en changeant d'album. »
- [x] Sous `lectrice`, fiche d'« esther v1 » : ni « ✎ Modifier l'album », ni « ✔ Tout valider », ni « Supprimer… » ; colonne *Validée*, un ✔ vert non cliquable ou un tiret ; pas de corbeille ; *Sur les collections* montre « Collection Test » cochée et ÉTEINTE, dont l'infobulle dit « Vous lisez cette collection sans y écrire »

### L'adresse — compte `proprio`, puis `lectrice`

- [x] Ouvrir `https://bd.127-0-0-1.sslip.io/corpus` dans un NOUVEL onglet, puis cliquer le nom « Collection Test » : l'adresse se termine par `?collection=N` ; cliquer l'onglet *Albums* : `&onglet=albums` s'y ajoute ; ouvrir « Calque A QA » depuis le tableau : `?collection=N&album=M`
- [x] F5 sur cette adresse : la fiche de « Calque A QA » se rouvre, avec « ← Collection Test » ; Précédent : la fiche de « Collection Test » revient sur *Albums* ; Précédent encore : la fiche du projet
- [x] Sous `proprio`, ouvrir « Étude B » et copier son adresse ; sous `lectrice`, coller cette adresse : la fiche du projet s'ouvre, avec en tête, en rouge, « La collection demandée n'est pas dans la liste : elle ne vous est pas ouverte, ou elle n'existe pas. » — sans dire laquelle des deux

### À l'étroit et à grande police — compte `proprio`, outils de développement en mode appareil

- [x] 375 px, Bibliothèque rechargée sans rien après `/corpus` : le bloc « Collections » et la liste des albums, puis la fiche du projet SOUS la liste, sans bouton « ← Liste » ; rien ne défile de côté
- [x] 375 px, cocher « Collection Test » et « Étude B » : la comparaison se lit sous la liste, son tableau défile dans son cadre si besoin, la page non
- [x] 375 px, toucher le nom « Collection Test » : la fiche REMPLACE la liste, « ← Liste » en tête ; onglet *Albums* : chaque album est une CARTE — son titre, ✎ et « Supprimer… » entiers, puis « Planches : 2 », « Validées : … », « Aussi dans : Étude B » ; « ← Liste » ramène la liste, le focus sur la collection courante
- [x] 320 px, fiche de « Calque A QA » : chaque planche est une carte, et 🏷 · 🔓 · ↗ · 🗑 se voient entiers après le numéro, sans défilement de côté ; les boutons de tête passent à la ligne sans se couper
- [x] 320 px, menu « Aa » → « A+ » jusqu'au plus grand : dans la fiche de « Calque A QA », la corbeille 🗑 de chaque carte reste visible et se touche au doigt ; dans la fiche de « Collection Test », les quatre onglets passent à la ligne sans en couper un ; « ↺ » ramène à 100 %
- [x] Fenêtre de bureau à pleine largeur (1 400 px ou plus), fiche de « Collection Test », onglet *Albums* : un TABLEAU avec ses en-têtes ; en rétrécissant la fenêtre vers 900 px, le tableau devient des cartes avant de déborder de sa colonne

### Rendre la recette — `C:\temp\bd-recette\etat-de-base.ps1`, puis compte `proprio`

- [x] `C:\temp\bd-recette\etat-de-base.ps1 restaurer` répond « bd-app : healthy » (ou « running »)
- [x] Sous `proprio`, Bibliothèque rechargée : « Collections · 2 », aucun album « … QA » dans la liste, et « esther v1 » est là
