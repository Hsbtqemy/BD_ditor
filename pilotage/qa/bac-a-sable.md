---
passe: Le bac à sable — l'ouvrir, y travailler à deux, le remettre à neuf, l'effacement, l'administrateur
chantier: COL-4
duree: 30 min
derniere: jamais
---

# QA — « Mon bac à sable », du premier clic d'un arrivant à l'effacement du lundi

**Écrite le 2026-10-24 sur la recette reconstruite sur `5aa166d`**, décor de l'état `avant-bac-a-sable` : la
v35 migrée sur la base de recette, le jeu préparé par `tools/preparer_jeu.py` avec sept planches de Digital
Comic Museum, hors du dépôt — part dépôt : *Bibi Fricotin chez les Chinois* (le parcours, découpé en trois
cases et quatre bulles sans texte), *L'École de Saint-Cyr* (Girin),
*Lightning Comics* n° 6 (deux pages), *Modern Comics* n° 76 ; part serveur : *Moustache et Trottinette*,
*Radar* — et aucun bac à sable ouvert. Non jouée. Elle porte sur l'écran tranché sur maquette le 2026-10-24
(`pilotage/COL-4.md`, zone « L'écran ») et sur le côté serveur qui le porte.

**Les comptes** : `invite` (des groupes, aucun accès : l'arrivant), `proprio` (titulaire d'un projet),
`lectrice` (l'invitée), `admin-bd` (administrateur), `collectif` (login partagé). Une fenêtre privée par
compte. **Ce que la passe ne juge pas** : 320 px et la grande police (mesurés par les tests, dans l'image
aussi) ; ShareDocs, que la recette n'a pas.

## Reste

### Le premier clic d'un arrivant — compte `invite`, Atelier

- [ ] Sur l'Atelier (`/`), le bandeau « Aucune collection ne vous est ouverte. » porte à droite « Mon bac à sable », visible sans déplier le bandeau
- [ ] « Mon bac à sable » est offert aussi dans la bande du haut et sous « Sélectionnez ou importez une planche pour commencer » ; le menu du compte (la pastille) ne l'offre pas
- [ ] Un clic sur « Mon bac à sable » du bandeau → l'Atelier ouvre la planche de *Bibi Fricotin chez les Chinois*, la bande dit le projet « Mon bac à sable », et le bandeau « Aucune collection… » a disparu
- [ ] Sous la bande, une rangée rayée dit « Bac à sable · s'efface lundi <jour> <mois> à 4 h · 0 / 50 planches importées », et à droite « Inviter… » et « Remettre à neuf… » ; le survol de « Bac à sable » donne l'aide
- [ ] La date est un lundi à 4 h, heure de Paris : pour une ouverture le 24 octobre 2026, « lundi 26 octobre à 4 h »
- [ ] Atelier, `t` (Transcription) sur la première bulle, taper `zygomar`, Entrée → la bulle suivante s'ouvre ; revenir sur la première : `zygomar` y est
- [ ] Bibliothèque : la rangée rayée y est aussi, les chiffres disent les albums du jeu (6 albums, 7 planches) et non « 0 » ; la fiche du projet n'offre pas « + Prendre du fonds… »
- [ ] Recherche : la rangée rayée y est ; chercher `zygomar` → aucun résultat (la Recherche ne voit aucun bac à sable) ; Exploration : la rangée y est aussi

### Recliquer ramène — compte `invite`

- [ ] Le sélecteur de projet de la bande liste « Mon bac à sable » ; la bande n'offre plus le bouton « Mon bac à sable »
- [ ] Fermer la fenêtre privée de `invite`, en rouvrir une, se reconnecter et ouvrir l'Atelier : c'est le même bac à sable — *Bibi Fricotin*, `zygomar` dans la première bulle —, et le sélecteur ne propose qu'un « Mon bac à sable »

### Inviter et travailler à deux — `invite` puis `lectrice`

- [ ] `invite`, « Inviter… » → le dialogue « Qui y entre » : `invite` « responsable », une ligne « Faire entrer » ; aucun choix de rôle, aucun groupe, aucune liste de l'annuaire
- [ ] Taper `lectrice`, « + Faire entrer » → elle apparaît « membre », avec ✕ ; Échap ferme, et le libellé de la rangée devient « Inviter… (1) »
- [ ] `lectrice`, recharger : le sélecteur de projet propose « Bac · invite », entier ; le choisir → la rangée dit « Bac à sable de invite · s'efface lundi … », avec « Quitter… » seul (ni « Inviter », ni « Remettre à neuf », ni compteur d'import)
- [ ] `lectrice`, Atelier, dans « Bac · invite », planche de *Bibi Fricotin*, `t` sur la DEUXIÈME bulle, taper `zorglub`, Entrée → `invite`, F5 sur la même planche, lit `zorglub` dans la deuxième bulle
- [ ] `lectrice`, Recherche : chercher `zorglub` → aucun résultat

### Le plafond d'import — compte `invite`, Bibliothèque

- [ ] Fiche de l'album *L'École de Saint-Cyr*, « ⤓ Importer des planches… », une image JPEG (par exemple une de `C:\Users\hsemil01\Documents\IGE\BDcorpus`) → elle s'ajoute à l'album, et la rangée dit « 1 / 50 planches importées »

### Remettre à neuf — compte `invite`

- [ ] « Remettre à neuf… » → « Remettre votre bac à sable à neuf ? » en deux colonnes : « Ce qui part » nomme la planche importée et l'invitation de `lectrice` ; « Ce qui revient » les albums du jeu ; le focus est sur « Annuler »
- [ ] « Annuler » → rien n'a changé (la planche importée est là, « Inviter… (1) »)
- [ ] Depuis l'Atelier, « Remettre à neuf… » puis « Remettre à neuf » → le message « Bac à sable remis à neuf. », l'Atelier sur la planche de *Bibi Fricotin*, ses bulles de nouveau vides (ni `zygomar` ni `zorglub`), « 0 / 50 », « Inviter… » sans nombre
- [ ] `lectrice`, recharger : « Bac · invite » a disparu du sélecteur, et un message dit qu'elle n'est plus dans le bac à sable de `invite`

### Quitter — `invite` réinvite `lectrice`

- [ ] `invite` refait entrer `lectrice` ; `lectrice`, dans « Bac · invite », « Quitter… » → une ligne « Quitter le bac à sable de invite ? », « invite pourra vous inviter à nouveau. », [Annuler] [Quitter]
- [ ] « Quitter » → le projet disparaît du sélecteur de `lectrice` ; chez `invite`, après F5, « Inviter… » ne compte plus personne

### L'administrateur — compte `admin-bd`

- [ ] Administration → Projets : un axe « Projets · n / Bacs à sable · 1 » ; « Bacs à sable » liste `invite`, « ouvert le JJ/MM », et en tête « tous s'effacent lun. 26 oct., 4 h » ; aucun bouton d'effacement ni « + Nouveau projet » de ce côté
- [ ] La fiche du bac de `invite` : le propriétaire (son nom mène à sa fiche dans « Comptes et groupes »), « Ouvert », « S'efface », et « Vous n'y entrez pas. Pour aider invite, faites-vous inviter. »
- [ ] Le sélecteur de projet de `admin-bd` ne propose pas le bac à sable de `invite` ; la Bibliothèque ne montre aucun de ses albums
- [ ] `admin-bd` ouvre son propre bac à sable (« Mon bac à sable » dans la bande) : la rangée est celle d'un arrivant ; l'axe dit « Bacs à sable · 2 », et la fiche de son bac dit « Votre bac à sable »

### Le compte partagé — `admin-bd` puis `collectif`

- [ ] `admin-bd`, Administration → 👥 Comptes et groupes, fiche de `collectif` : sélecteur **Nature** sur « un login partagé » → « Nature enregistrée. »
- [ ] `collectif`, Atelier, F5 : ni le bandeau, ni la bande, ni la page vide n'offrent « Mon bac à sable »

### L'effacement du lundi — `invite`, Atelier ouvert dans son bac à sable ; PowerShell

- [ ] Lancer `docker exec bd-app python tools/effacer_bacs_a_sable.py --maintenant "2026-10-26 03:00:01"` → il dit « À blanc : 2 bac(s) à sable à effacer », sans rien effacer
- [ ] Le relancer avec `--appliquer` en plus → il dit les avoir effacés ; puis, `invite`, ouvrir la Bibliothèque : un message dit que son bac à sable a été effacé, la page est vide, et « Mon bac à sable » est de nouveau offert dans la bande et le bandeau ; le message ne revient pas en rouvrant l'Atelier
- [ ] Un nouveau clic sur « Mon bac à sable » rouvre un bac à sable neuf, sur la planche du parcours

### Rendre la recette — PowerShell

- [ ] `C:\temp\bd-recette\etat-de-base.ps1 restaurer avant-bac-a-sable` finit par « bd-app : running »
