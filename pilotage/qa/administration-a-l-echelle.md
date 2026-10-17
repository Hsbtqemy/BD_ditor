---
passe: L'Administration à l'échelle
chantier: COL-3
duree: 60 min
derniere: —
---

# QA — l'Administration à l'échelle : cinq vues adressables, « À faire », le fonds et les projets en liste et fiche

**Écrite le 2026-10-17, non jouée.** Elle porte sur `73241cc` (les cinq vues, « À faire », le
fonds en liste et fiche) et `ec56a73` (la vue Projets), et sert la liste « À faire valider par
Hugo sur la recette » de la case « L'Administration tient à l'échelle » de la fiche `COL-3`.

**Ce que les tests couvrent déjà — ne pas le refaire ici** : les requêtes parties de chaque
geste, les codes de réponse, la garde de chaque vue et de chaque bloc (un lien de vue ne se
lève que si sa route a répondu), la forme des réponses. **Ce qui se regarde ici** : ce que
l'écran DIT, s'il se comprend avant d'agir, et si l'on s'y repère — d'où l'on part, où l'on
arrive, ce que l'adresse et le bouton Précédent font de nous.

**Ce que la passe ne juge pas**, parce que ce n'est pas encore écrit : la vue Instance, qui
reste en blocs empilés ; le lien « ← Retour » de la bande du haut ; un filtre par état et un
tri dans la liste des projets. Les deux réponses à « Supprimer… » dans la Bibliothèque ont leur
passe, `supprimer-n-est-pas-sortir` : on ne s'en sert ici que pour poser le décor.

Les zones se jouent DANS L'ORDRE : chacune s'appuie sur ce que la précédente a laissé. Le décor
se construit dans les cases, la dernière zone le rend.

### Le décor de départ — `C:\temp\bd-recette\etat-de-base.ps1`, puis compte `admin-bd`, Administration

- [ ] `C:\temp\bd-recette\etat-de-base.ps1 restaurer` répond « bd-app : healthy » (ou « running ») — la passe crée et détruit des albums, un projet, une collection : la dernière zone rend la recette
- [ ] Sous `admin-bd` (une fenêtre privée par compte, pour toute la passe), ouvrir `https://bd.127-0-0-1.sslip.io/administration?vue=instance` : « 🏷️ Version servie » affiche le commit `ec56a73` ou plus récent — sur un serveur plus ancien, la vue Projets n'existe pas et rien de ce qui suit ne mesure

### Le menu des vues et l'adresse — compte `admin-bd`, Administration

- [ ] Sous le titre « Administration », le menu porte cinq liens dans cet ordre : « À faire », « Fonds 3 » (les trois albums de la recette sont ses trois documents), « Projets », « Comptes et groupes », « Instance » ; celui de la vue affichée est encadré de bleu et en gras, les autres non
- [ ] Cliquer tour à tour « Fonds », « Projets », « Comptes et groupes », « À faire » : l'adresse se termine à chaque clic par `?vue=fonds`, `?vue=projets`, `?vue=comptes`, `?vue=afaire`, et la page ne montre que le bloc de cette vue — seule « Instance » en montre trois
- [ ] Bouton Précédent du navigateur, quatre fois : la page repasse par « Comptes et groupes », « Projets », « Fonds », « Instance », et l'adresse comme le lien marqué suivent à chaque fois
- [ ] Taper l'ancienne adresse `/administration?compte=lectrice`, sans `vue=` : la page s'ouvre sur « Comptes et groupes », la fiche de `lectrice` ouverte, et c'est le lien « Comptes et groupes » qui est marqué
- [ ] « Fonds », cliquer « esther v1 » dans la liste : l'adresse devient `…?vue=fonds&document=N` ; y effacer `vue=fonds&` et valider : la page s'ouvre sur « Fonds », la fiche d'« esther v1 » ouverte (ne rien y toucher : d'autres passes dépendent de cet album)

### Construire ce qui attend — comptes `proprio`, `stagiaire`, `admin-bd`

- [ ] Sous `proprio`, Bibliothèque, **+ Nouvel album** trois fois, *Collection* = « Collection Test », dans cet ordre : « Garder QA », « Détruire QA », « Retrait QA ». Les trois lignes apparaissent, 0 planche
- [ ] Sous `proprio`, *Supprimer…* sur « Retrait QA » → « Supprimer de « Collection Test » » : « « Retrait QA » n'est plus dans « Collection Test ». Sa copie de travail est gardée au fonds. » s'affiche
- [ ] Sous `stagiaire`, Bibliothèque, *Supprimer…* sur « Garder QA », seconde carte : un motif, la case de certification cochée, « Envoyer la demande » ; la ligne porte « suppression demandée par vous ». ENSUITE, le même geste sur « Détruire QA » — l'ordre compte : l'alphabet et le dépôt ne rangent pas pareil
- [ ] Sous `admin-bd`, Bibliothèque, « 📚 Collections », créer « Sans tête QA » (**+ Créer**) : le message commence par « « Sans tête QA » créée. Vous l'administrez comme administrateur de l'instance, sans en être propriétaire : » — elle naît sans propriétaire
- [ ] Sous `admin-bd`, Administration, « Projets », **+ Nouveau projet** (en tête de la liste) : la fiche devient « Nouveau projet », le champ *Nom* a le focus, l'aide dit « 21 caractères au plus : le nom se lit en haut de chaque page, où il ne se coupe pas. » ; *+ Créer le projet* sans nom affiche « Donnez un nom au projet. »
- [ ] Nom « Projet QA », *+ Créer le projet* : « « Projet QA » créé. Il est vide : faites-y entrer quelqu'un dans sa fiche, puis créez-y une collection depuis la Bibliothèque. », sa fiche s'ouvre, l'adresse se termine par `&projet=N`, et sa ligne dans la liste porte « ⚠ sans responsable »
- [ ] Dans sa fiche, *Qui y entre* : *Faire entrer* → « Un compte, ou un groupe absent de la liste… », `proprio`, « Compte », *+ Faire entrer*, puis passer sa ligne à « responsable du projet » : sans recharger, « ⚠ sans responsable » quitte sa ligne de la liste et la puce « sans responsable » quitte la fiche
- [ ] Sous `proprio`, Administration, « Projets », fiche de « Projet QA », partie *Ce projet* : « Demander sa suppression… », un motif, « Envoyer la demande » : la puce « suppression demandée le JJ/MM/AAAA » remplace le bouton

### L'ouverture quand quelque chose attend — compte `admin-bd`, Administration

- [ ] Le lien « À faire » du menu porte maintenant un nombre, en ambre et en gras : 4 — trois demandes et la collection sans propriétaire (5 si « 📇 Référent de l'instance », vue « Instance », dit que personne n'est désigné ou qu'il n'a aucun contact)
- [ ] La dernière vue consultée étant « Projets », ouvrir `/administration` (rien après) dans un nouvel onglet : la page s'ouvre sur « À faire » ; puis ouvrir `/administration?vue=fonds` : elle s'ouvre sur « Fonds » — l'adresse prime sur ce qui attend

### Le fonds — compte `admin-bd`, vue « Fonds »

- [ ] **+ Importer au fonds** (en tête de la liste) : la fiche devient « Importer au fonds » et dit « L'album naît appelé par personne, sans projet ; « Rendre » le range ensuite dans une collection. » ; *+ Importer au fonds* sans titre affiche « Donnez un titre à l'album. », et rien n'est créé
- [ ] Titre « Fonds QA », une image JPEG ou PNG du poste, *+ Importer au fonds* : « « Fonds QA » est au fonds, appelé par personne : 1 planche importée. » s'affiche, sa fiche s'ouvre, et l'adresse porte `&document=N`
- [ ] Sous le titre du bloc : « 7 documents · 2 appelés par personne · 3 suppressions demandées » (la troisième est celle du projet, qu'aucune ligne du fonds ne porte) ; le menu dit « Fonds 7 »
- [ ] Les boutons d'état portent leurs nombres — « Tous 7 », « Demandés 2 », « Appelés par personne 2 », « Copies gardées 1 » — et chacun, cliqué, ne garde que ses lignes : « Garder QA » et « Détruire QA » ; « Retrait QA » et « Fonds QA » ; « Retrait QA » seul — le compte au-dessus de la liste disant « 2 sur 7 », « 2 sur 7 », « 1 sur 7 »
- [ ] « Tous », puis la fiche de « Fonds QA » : sa ligne dit « appelé par personne », « Copies gardées » ne le compte pas, et sa fiche dit « Copie gardée ici (sans projet). » — ces mots se comprennent ensemble à la lecture (sinon ne pas cocher, et noter ce qui gêne)
- [ ] Filtre texte : `qa` ne garde que les quatre documents de la passe (« 4 sur 7 ») ; `zzz` affiche « Aucun document ne répond à ces filtres. » ; vider le champ
- [ ] *Projet* propose « Tous », « Sans projet », « Projet principal », et « Sans projet » ne garde que « Fonds QA » ; *Importé par* propose « Tous », « Non écrit (avant le fonds) », puis les noms d'`admin-bd` et de `proprio`, et « Non écrit (avant le fonds) » ne garde que les trois albums de la recette. Remettre « Tous » aux deux
- [ ] Tri « Récents d'abord » (enfoncé à l'ouverture) : « Fonds QA », « Retrait QA », « Détruire QA », « Garder QA » en tête, dans cet ordre ; « A → Z » : « Annee_lievre-1 », « Détruire QA », « Eau-terre », « esther v1 »… (la casse n'y compte pas : « esther v1 » vient après « Eau-terre ») ; « Par projet » : un intertitre « Projet principal », et « Sans projet » en dernier, sur « Fonds QA »
- [ ] Fiche de « Retrait QA » : sous le nom « 0 planche » et la puce « copie gardée » ; *Origine* « Importé par … (proprio), le JJ/MM/AAAA, dans « Projet principal ». » ; *Employé dans* « Aucune collection. » puis « Copie gardée ici (projet « Projet principal »). », une liste et *Rendre* ; en bas *Détruire* et « Personne ne l'appelle : il peut être détruit. »
- [ ] Dans cette fiche, choisir « Étude B » → *Rendre* : « Copie rendue à « Étude B », avec tout son travail. » ; la puce devient « 1 collection », *Employé dans* dit « Employé par Projet principal : Étude B », *Détruire* a disparu, et le bouton d'état dit « Copies gardées 0 »
- [ ] Fiche de « Garder QA » : une section « Suppression demandée » — « suppression demandée par … le JJ/MM/AAAA. », le motif, et « Répondre dans « À faire » → » ; ce bouton ouvre la vue « À faire », la demande de « Garder QA » dépliée et encadrée par le focus ; *Replier*
- [ ] Précédent : la vue « Fonds » revient sur la fiche de « Garder QA » ; ouvrir celle d'« esther v1 » puis Précédent : « Garder QA » revient ; copier l'adresse et l'ouvrir dans un nouvel onglet : la même fiche s'ouvre, vue « Fonds »
- [ ] Fiche de « Fonds QA », *Détruire* : la confirmation dit « Détruire « Fonds QA » ? Ses images et tout le travail fait dessus sont effacés, dans tous les projets. Irréversible. » ; l'accepter : « « Fonds QA » : détruit, avec ses images et tout le travail fait dessus. », la ligne part, la fiche dit « Choisissez un document dans la liste pour ouvrir sa fiche. », et l'adresse ne porte plus `document=`

### Projets — compte `admin-bd`, vue « Projets »

- [ ] La liste dit « 2 projets » ; « Projet principal » porte son nombre de collections et AUCUN « ⚠ » — il n'a pas de responsable, mais c'est le projet de repli ; « Projet QA » porte « 0 collection » et « ⚠ suppression demandée »
- [ ] Filtre `qa` : « 1 sur 2 », seule « Projet QA » reste ; `zzz` : « Aucun projet ne répond à ce filtre. » ; vider le champ
- [ ] Fiche de « Projet principal » : la puce « projet de repli », aucune puce « sans responsable », la phrase « C'est le projet de repli : une collection créée sans nommer de projet y est rangée. Il se renomme, il ne se supprime pas. », et aucun bouton « Supprimer le projet »
- [ ] Fiche de « Projet QA » : sous le nom « 0 collection » et la pastille « suppression demandée » ; *Qui y entre* nomme `proprio`, « responsable du projet » ; « Supprimer le projet » est là — NE PAS cliquer : la demande se répond dans « À faire »
- [ ] Fiche de « Projet QA » ouverte, copier l'adresse (`…?vue=projets&projet=N`) dans un nouvel onglet : la même fiche s'ouvre ; dans le premier onglet, ouvrir « Projet principal » puis Précédent : « Projet QA » revient

### Une vue absente pour qui n'y a pas droit — comptes `proprio` et `arrivant`, Administration

- [ ] Sous `proprio`, `/administration` : le menu n'offre que « Projets » et « Instance » ; la liste des projets ne montre que « Projet QA », avec « ⚠ suppression demandée », et il n'y a pas de bouton « + Nouveau projet »
- [ ] Sous `proprio`, taper `/administration?vue=fonds`, puis `/administration?vue=comptes&compte=arrivant` : ni bloc du fonds ni fiche de compte, aucun message d'erreur ; la page montre à chaque fois « Projets » (ou « Instance », s'il l'a consultée en dernier)
- [ ] Sous `arrivant`, `/administration` : le menu n'offre ni « À faire », ni « Fonds », ni « Comptes et groupes », et la page s'ouvre sur une vue qui montre quelque chose — « Instance », ou « Projets » s'il est membre d'un projet, qui dit alors « Les projets se règlent par leur responsable. … » — jamais une page vide

### Comptes et groupes, Instance — ce qui n'a pas changé ; compte `admin-bd`, Administration

- [ ] « Comptes et groupes », « ⚠ À regarder » : ses trois premières lignes sont les demandes (« … demande la suppression définitive de « Garder QA » », puis « Détruire QA », puis « … demande la suppression du projet « Projet QA » ») ; cliquer la première ouvre la vue « À faire », cette demande dépliée, l'adresse disant `?vue=afaire` ; *Replier*
- [ ] « Comptes et groupes », axe *Collections*, fiche de « Sans tête QA » : la puce rouge « sans propriétaire » ; axe *Comptes*, filtre `lectrice`, sa fiche : l'adresse dit `?vue=comptes&compte=lectrice` ; Précédent : la fiche se referme, et l'adresse a perdu `compte=`
- [ ] « Instance » : trois blocs, dans cet ordre — « 🏷️ Version servie », « 📇 Référent de l'instance », « 🩺 Moteurs de reconnaissance » — et aucun autre ; si le référent dit « Personne n'est désigné. » ou « aucun contact déclaré », « À faire » a un groupe *Instance* qui le dit, avec « Voir → » qui ramène ici

### À l'étroit et à grande police — compte `admin-bd`, outils de développement en mode appareil

- [ ] 375 px, vue « Fonds » : les filtres et la liste seuls ; choisir « Garder QA » : sa fiche SEULE, « ← Liste » en tête ; « ← Liste » ramène la liste, le focus sur la ligne choisie ; même geste dans « Projets » sur « Projet QA » ; rien ne défile de côté
- [ ] 320 px, vue « Fonds » : les quatre boutons d'état et leurs nombres, *Projet* et *Importé par* se lisent en entier dans la largeur, sans défilement de côté
- [ ] 320 px : le menu des vues passe à la ligne sans couper un lien ni faire défiler la page de côté ; vue « À faire », *Répondre* sur « Garder QA » : le motif, « Détruire » et « Garder » se lisent entiers, sans défilement de côté ; *Replier*
- [ ] Fenêtre ordinaire, menu « Aa » → « A+ » jusqu'à 150 % : le menu des vues reste lisible (il passe à la ligne s'il le faut), et dans « Fonds » rien ne défile de côté — liste et fiche côte à côte, ou une colonne à la fois avec « ← Liste » ; « ↺ » ramène à 100 %

### « À faire » : lire, puis répondre sur place — compte `admin-bd`, vue « À faire »

- [ ] Les groupes viennent dans cet ordre : « Demandes », « Accès à régler » (« Instance » ensuite, si le référent manque) ; sous « Demandes » : « Garder QA », puis « Détruire QA », puis « Projet QA » — l'ordre du dépôt, le plus ancien d'abord, et non l'alphabet
- [ ] Une demande de document dit, en petit, « Supprimer un document », puis « … demande la suppression définitive de « Garder QA » », puis « le JJ/MM/AAAA · depuis « Projet principal » », et un bouton *Répondre* ; celle du projet dit « Supprimer un projet », « … demande la suppression du projet « Projet QA » », et « le JJ/MM/AAAA » seul
- [ ] *Répondre* sur « Garder QA » : la ligne se déplie sur place — le motif, « Certifié par … le JJ/MM/AAAA : ces données ne sont pas importantes. », « Importé par … (proprio). », « Gestes d'autres personnes, lus au journal — un geste défait depuis compte encore : » et une ligne pour `proprio`, puis « Détruire » (rouge) et « Garder » ; le bouton dit maintenant « Replier »
- [ ] *Garder* : « « Garder QA » : gardé. La demande de … est close. » s'affiche en tête du bloc, la ligne part, le nombre du menu baisse d'un, et le focus est sur le titre « À faire »
- [ ] *Répondre* puis *Détruire* sur « Détruire QA » : la confirmation dit « Détruire « Détruire QA » ? Ses images et tout le travail fait dessus sont effacés, dans tous les projets. Irréversible. » ; l'accepter : « « Détruire QA » : détruit, avec ses images et tout le travail fait dessus. », et la ligne part
- [ ] *Répondre* puis *Supprimer le projet* sur « Projet QA » : la confirmation dit « Supprimer le projet « Projet QA » ? Ses membres en sortent. Il ne se supprime que vide. » ; l'accepter : « Le projet « Projet QA » est supprimé. », le groupe « Demandes » disparaît, et la vue « Projets » ne liste plus que « Projet principal »
- [ ] « Accès à régler » : « « Sans tête QA » n'a pas de propriétaire », *Régler →* : la vue « Comptes et groupes » s'ouvre sur la fiche de « Sans tête QA » ; dans *Qui entre*, faire entrer le compte `proprio` (« Un compte, ou un groupe absent de la liste… », « Compte ») et cocher « décider qui entre »
- [ ] Revenir à « À faire » : « Rien n'attend de geste. », et le lien du menu n'a plus de nombre ; s'il y a des comptes jamais venus, un repli FERMÉ « N comptes jamais venus — à titre d'information » (au singulier s'il n'y en a qu'un), dont chaque ligne mène à la fiche du compte

### L'ouverture quand rien n'attend — compte `admin-bd`, Administration

- [ ] Outils de développement → *Application* → *Stockage local* de `https://bd.127-0-0-1.sslip.io` : supprimer la clé `bd-admin-vue`, puis ouvrir `/administration` (rien après) : la page s'ouvre sur « Comptes et groupes »
- [ ] Cliquer « Fonds », puis ouvrir `/administration` dans un nouvel onglet : la page s'ouvre sur « Fonds », la dernière vue consultée ; y cliquer « À faire », puis rouvrir `/administration` : elle s'ouvre encore sur « Fonds » — « À faire » ne se retient pas

### Rendre la recette — `C:\temp\bd-recette\etat-de-base.ps1`, puis compte `admin-bd`

- [ ] `C:\temp\bd-recette\etat-de-base.ps1 restaurer` répond « bd-app : healthy » (ou « running »)
- [ ] Sous `admin-bd`, Administration rechargée : le menu dit « Fonds 3 », « Projets » ne liste que « Projet principal », et aucun « … QA » ne subsiste — ni au fonds, ni dans « Comptes et groupes », axe *Collections*
