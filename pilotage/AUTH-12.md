---
chantier: AUTH-12
statut: interrompu
---

# AUTH-12 — gérer les comptes : un parcours par personne, et non quatre outils à connaître

**Arrêté sur** — 2026-09-16, `abc3dc0` : les quatre défauts de code de la zone « Défauts trouvés en lisant » sont réparés et éprouvés. La Bibliothèque ne propose plus que les collections où l'on écrit — `GET /api/collections` renvoie `ecrivable`, sur le modèle d'`exportable` — et ne dit « propriétaire » qu'à qui l'est : une collection créée par un administrateur reste sans propriétaire (option B), et l'écran le dit. Avant lui, `749ceb8` (le journal des modifications, les gardes de `tools/gerer_collections.py`) ; et `e0ef3c7`, de la coordination, qui a retiré la phrase « zéro propriétaire interdit » de quatre textes. La passe de relecture demandée par Hugo a trouvé une phrase de plus qui promettait la propriété à tout créateur, la liste vide de l'Administration : corrigée par `abc3dc0`, avec un test qui éprouve enfin les deux listes vides. Le guide d'usage portait la même promesse ; la coordination le corrige. Reste la documentation d'usage, qui attend les décisions. **Les sept décisions sont tranchées par Hugo le 2026-09-17** : 1 (A), 2 (b), 3 (a), 4 (2), 5 (b), 6 (b), 7 adopté. Restent à proposer sur la maquette le nom du bloc (3) et les trois textes de la liste (4), puis à mesurer l'import en lot (5) et à écrire l'ordre de construction.

**Point de départ** — 2026-09-16, cadrage demandé par Hugo, sans code : *« travailler
l'interface fonctionnelle des comptes et des utilisateurs, pour leur gestion. Là, c'est
encore trop complexe entre Authelia, l'annuaire, et les paramètres dans Bibliothèque et dans
Administration »*. C'est le cap des prochaines semaines. Cette fiche écrit le parcours tel
qu'il se vit aujourd'hui, geste par geste ; le parcours visé ; et les décisions qui
séparent les deux, formulées pour Hugo avec leurs options et une recommandation. Rien n'est
engagé. **Validée par Hugo le même jour**, qui y a fait ajouter deux sections : la finesse
des droits, telle qu'`AUTH-10` la pose, dans l'écran d'attribution ; et la forme de l'écran,
choisie le même jour sur des maquettes interactives : une liste et une fiche, côte à côte.

**Pourquoi une fiche neuve, et pas une zone d'`AUTH-7`.** `AUTH-7` avait reçu une demande
voisine le 2026-09-06, avec un critère explicite — *« activer, désactiver, créer, attribuer,
potentiellement dans DEUX ESPACES SÉPARÉS […] Tant qu'on évite la console »* —, et en avait
tiré qu'il n'y avait **pas à unifier** : créer vit dans l'annuaire, attribuer dans
l'application. Elle l'a fait, et bien. La demande d'aujourd'hui dit précisément que cette
séparation, une fois construite, reste trop complexe. Loger ce constat dans la fiche qui a
conclu l'inverse l'y enterrerait sous 700 lignes de plomberie ouverte (repli, règle `deny`,
TOTP orphelin), et l'**Arrêté sur** d'`AUTH-7` cesserait de dire où en est cette plomberie.
Le sujet est aussi plus large : il regarde le compte depuis les QUATRE rôles — la personne,
le propriétaire d'une collection, l'administrateur, et l'administrateur système —, là où
`AUTH-7` regarde l'administrateur seul. `AUTH-6`, `AUTH-7`, `AUTH-9`, `AUTH-10`, `UX-4` et
`UX-14` restent les chantiers qui exécutent ; celui-ci dit dans quel ordre, et pourquoi.

## Reste

### Trancher — les décisions de Hugo
- [x] **Décision 1 — L'application ÉCRIT-elle dans l'annuaire ?** Options : **(A)** elle le LIT seulement (décision d'`AUTH-6` du 2026-09-09, jamais construite) et renvoie par un lien vers l'interface de LLDAP pour tout ce qui modifie un compte ou un groupe ; **(B)** elle écrit, pour les seuls administrateurs, dans LLDAP par son API — créer un compte, ranger dans un groupe —, les mots de passe et le second facteur restant au portail ; **(C)** un panneau tiers (`asalimonov/authelia-admin`, trois réserves non levées dans `AUTH-7`). **Recommandation : (A).** (B) retire un écran, mais il faut à l'application un identifiant de service qui CRÉE des comptes, donc `lldap_admin` (le commentaire de `deploy/authelia/configuration.yml` le dit : créer exige ce rôle, qui inclut supprimer) : qui compromet l'application — une application web qui reçoit des fichiers et lance des moteurs — se fabrique un membre de `bd-admins`. C'est le changement de catégorie qu'`AUTH-7` a écarté pour son « chemin 3 ». Attendu : l'option retenue et sa raison, et, si (A), ce qui rouvrirait (B) — le déclencheur qu'`AUTH-7` écrivait pour Authentik vaut ici : une délégation large, « chaque enseignant inscrit sa classe » — **tranché par Hugo le 2026-09-17 : (A)**, pour la raison ci-dessus. (B) se rouvre sur ce déclencheur-là, et sur lui seul
- [x] **Décision 2 — Où règle-t-on qui entre dans UNE collection ?** Options : **(a)** là où `COL-2` l'a tranché deux fois le 2026-09-10 — l'Administration, parce que « qui entre relève de l'instance » ; **(b)** dans la collection elle-même, dans la Bibliothèque, à côté de sa description, l'Administration gardant la vue TRANSVERSE : les personnes, les groupes, et qui a accès à quoi à travers toutes les collections. **Recommandation : (b), dans le même geste que la refonte du panneau (`UX-4`) et le choix dans l'annuaire, jamais avant.** Ce qui justifie de rouvrir une décision de six jours : la demande nomme la répartition elle-même comme source de la complexité, et le trajet le plus courant d'un propriétaire qui n'administre rien — créer sa collection, puis y faire entrer ses étudiants — traverse aujourd'hui deux écrans, dont un intitulé « ce qui porte sur l'instance ». L'axe de (b) n'est plus instance / corpus mais **une collection / toutes**. Ce que (b) coûte : un second déménagement de code qui vient d'être déplacé, et les audits qui l'épinglent. Attendu : l'option et sa raison ; si (b), la phrase de frontière de `COL-2` réécrite par un renvoi posé dans `COL-2`. **Les deux options sont dessinées dans la maquette de la forme 1**, le 2026-09-16 — (a) un lien « Décrire dans la Bibliothèque ↗ » dans la fiche de la collection, (b) Description, Diffusion, Référent et Exports repliés dans la même fiche —, et **non tranchées** — **tranché par Hugo le 2026-09-17 : (b)**, dans le même geste que la refonte du panneau (`UX-4`) et la lecture de l'annuaire, jamais avant. Rien n'a encore déménagé. Le renvoi est posé dans `COL-2`, sur sa case « Où vit l'écran »
- [x] **Décision 3 — Où vivent les personnes et les groupes, vus par l'administrateur ?** Options : **(a)** un bloc de l'Administration qui remplace « 👤 Comptes vus par l'application » ; **(b)** une sixième page `/comptes` — donc une surface de plus dans les listes des audits, de la CSP et de la navigation (mesuré par `UX-10`). **Recommandation : (a).** L'Administration est le lieu de l'instance (`UX-10`), et une personne est un fait d'instance. Attendu : l'option, et le nom du bloc — **option tranchée par Hugo le 2026-09-17 : (a).** Reste le NOM du bloc, à proposer sur la maquette et borné par le lexique de la décision 7 ; la case ne se coche qu'avec lui — **nommé par Hugo le 2026-09-17, sur la maquette : « 👥 Comptes et groupes »**, préféré à « Comptes, groupes et accès » et à « Qui utilise l'instance »
- [x] **Décision 4 — Le principal d'un accès se CHOISIT-il dans l'annuaire, ou se tape-t-il encore ?** Options : **(1)** liste seule, rien hors de l'annuaire ; **(2)** liste, plus une saisie libre signalée « inconnu de l'annuaire » ; **(3)** saisie libre, comme aujourd'hui. **Recommandation : (2)**, et une panne de lecture dit « je n'ai pas pu vérifier » sans bloquer le geste — l'attendu (c) d'`AUTH-6`. (1) empêcherait d'accorder un accès à un groupe qu'on crée dans l'heure, et rendrait l'application inutilisable quand l'annuaire ne répond pas. La liste propose les GROUPES d'abord : c'est le principal qu'`AUTH-6` a retenu pour un cours. Attendu : l'option, et ce que l'écran dit dans chacun des trois cas — trouvé, inconnu, lecture impossible — **option tranchée par Hugo le 2026-09-17 : (2)**, les groupes en tête. Restent les trois textes, à proposer sur la maquette ; la case ne se coche qu'avec eux — **textes de la maquette retenus le 2026-09-17**, Hugo n'y tenant pas autrement : trouvé, aucune marque (« Le groupe X entre dans « Collection Test », en lecture ») ; inconnu, « Le groupe X n'est pas dans l'annuaire : l'accès est accordé, en lecture, mais n'ouvrira rien tant que ce nom n'y existe pas », et la ligne marquée « inconnu de l'annuaire » ; lecture impossible, une note sous la ligne d'ajout (« L'annuaire ne répond pas : impossible de proposer ses groupes et ses comptes, ni de vérifier le nom que vous tapez. L'accès sera accordé tel quel, et marqué « non vérifié » ») et la ligne marquée « non vérifié ». Un nom tapé exige de dire « Compte » ou « Groupe », et un refus garde la saisie
- [x] **Décision 5 — L'arrivée d'une promotion accepte-t-elle UN geste hors écran par rentrée ?** Le pic est le problème qu'`AUTH-7` a chiffré — jusqu'à trente personnes la même semaine — et l'interface de LLDAP crée un compte par formulaire. Options : **(a)** trente formulaires ; **(b)** un import en lot (fichier CSV ou script de LLDAP) lancé par l'administrateur système, une fois, documenté dans `docs/exploitation.md` ; **(c)** un import dans l'application, qui suppose (B) ci-dessus. **Recommandation : mesurer (b) sur la pile de recette avant de trancher** — trente comptes fictifs, jamais les comptes existants, qui portent le décor des passes. Le critère fondateur d'`AUTH-7` était « sans console » ; une console une fois par rentrée, tenue par qui a déjà le serveur, n'est pas le geste qu'il voulait supprimer — mais c'est à Hugo de le dire. Attendu : l'option, sur la mesure — **tranché par Hugo le 2026-09-17 : (b)**, sans attendre la mesure. Elle devient la première étape (zone « Mesurer, avant de construire ») : si elle montre l'import inutilisable, la décision se rouvre
- [x] **Décision 6 — Le référent de l'INSTANCE se voit-il depuis l'écran ?** Aujourd'hui `BD_REFERENT_NOM` / `BD_REFERENT_CONTACT` ne se posent qu'en SSH, dans `.env`, et ne s'affichent qu'à qui ne voit rien ; un `.env` recréé repartirait sans eux, sans signal (`AUTH-6`). Options : **(a)** rien ne change ; **(b)** l'Administration l'AFFICHE aux administrateurs, avec « se règle dans l'environnement du serveur » ; **(c)** il se règle dans l'Administration, stocké en base. **Recommandation : (b)** — le coût est une ligne de lecture, et le réglage change rarement. (c) si le référent change plus d'une fois par an. Attendu : l'option — **tranché par Hugo le 2026-09-17 : (b)**
- [x] **Décision 7 — Un seul vocabulaire sur les trois outils** — portail, annuaire, application. Aujourd'hui un même écran s'appelle « Comptes vus par l'application », « Comptes vus », « la vue des comptes » ou « sous la liste du panneau Collections » selon le document, et « compte », « login », « principal », « utilisateur » désignent tantôt la même chose, tantôt non. Proposition : **compte** (un login, nominatif ou partagé), **personne** (un compte nominatif), **groupe** (un ensemble de comptes, défini dans l'annuaire), **accès** (ce qu'un compte ou un groupe peut faire dans UNE collection), **propriétaire** (le niveau qui décide des accès), **administrateur** (membre de `bd-admins`, qui voit tout). Attendu : le lexique arrêté, et « principal » ou « genre » absents de tout texte d'écran — **lexique adopté par Hugo le 2026-09-17**, tel que proposé. Son application aux écrans est une case de la zone suivante

### Ce que les décisions engagent (2026-09-17)
- [x] **La maquette de la forme 1 est mise à jour sur les décisions, et Hugo la valide avant la construction** — attendu : la décision 2 en (b) seule, les accès d'une collection dans sa fiche ; le bloc de l'Administration de la décision 3, avec le NOM proposé ; la liste de la décision 4, groupes en tête, avec la saisie libre et les trois textes proposés — trouvé, inconnu de l'annuaire, lecture impossible ; le référent de l'instance affiché aux administrateurs, avec « se règle dans l'environnement du serveur » (décision 6) — **mise à jour le 2026-09-17 (versions 3 et 4 de la maquette)**, un débordement à 768 px relevé par Hugo et corrigé (liste et tableau des accès, mesuré à trois largeurs et trois rôles). Le nom et les textes sont retenus ; reste la présentation du référent de l'instance, sur laquelle Hugo ne s'est pas encore prononcé (« je ne vois pas ») — **validée le 2026-09-17.** Sur le référent, Hugo a un intérêt limité, et la coordination partage cet avis : utile à chaque rentrée, puisque seuls les bloqués le lisent et que personne ne remarque qu'il manque ou qu'il est périmé, mais secondaire. La décision 6 (b) est gardée telle quelle, sans maquette, et construite EN DERNIER
- [ ] **Aucun texte d'écran ne dit « principal » ni « genre »** — attendu : `templates/` et `static/` n'emploient, pour ce qu'ils montrent, que le lexique de la décision 7 — compte, personne, groupe, accès, propriétaire, administrateur. Aujourd'hui la ligne d'ajout d'un accès demande « Utilisateur ou groupe ? », ce qui est juste, mais ses messages de refus et ses attributs lisibles sont à relire
- [x] **L'ordre de construction est écrit ici, chantier par chantier** — attendu : ce qui vient d'abord (la lecture de l'annuaire d'`AUTH-6`, sans laquelle ni la liste de la décision 4 ni les membres d'un groupe n'existent), ce qui suit (le bloc de l'Administration, le déménagement des accès dans la Bibliothèque avec `UX-4`), et quel chantier porte chaque morceau — **validé par Hugo le 2026-09-17**, section « L'ordre de construction » ci-dessous

### La finesse des droits dans l'écran d'attribution
- [ ] **Les maquettes de l'écran d'attribution tiennent les issues d'`AUTH-10` SANS changer de gabarit** — attendu : trois états dessinés sur le même gabarit et les mêmes données : le modèle d'aujourd'hui (les quatre familles d'écriture cochées ENSEMBLE, leur liaison visible) ; le niveau `contribution` séparé (l'acte interprétatif détachable de la structure, du vocabulaire et des lots) ; une capacité hors rang ajoutée (le vocabulaire, sur le modèle d'« exporter »). Si l'un des trois oblige à redessiner, le gabarit est à reprendre avant de construire. Section « La finesse des droits » ci-dessous. **Dessiné le 2026-09-16, pas jugé** : la maquette de la forme 1 montre les trois issues sur le même gabarit et les mêmes données, les liaisons par une barre entre les cases, l'échelle qui coche les crans du dessous. Hugo s'est prononcé sur la forme, pas sur ces trois états : la case reste ouverte jusqu'à ce qu'il le fasse
- [ ] **L'écran ne connaît aucun niveau en dur** — attendu : la liste des actes, leur ordre et leurs liaisons lui sont DÉCRITS par le serveur, depuis l'endroit où `autorisation.py` les tranche ; ajouter un niveau ou une case hors rang ne touche pas au JavaScript de l'écran. C'est la condition pour que la décision d'`AUTH-10` arrive sans refaire l'écran, et la même règle que la garde : une seule source, côté serveur
- [ ] **La personne lit ce qu'elle peut FAIRE, pas le nom de son niveau** — attendu : « Mon compte » (`AUTH-9`) dit, par collection, les actes ouverts — et que supprimer un album y est possible et ne se rattrape pas, tant que c'est vrai (`AUTH-10`, « La décision du 2026-09-10 »). Même description que l'écran d'attribution, pour que les deux écrans ne puissent pas se contredire

### La forme de l'écran
- [x] **La forme se choisit sur des MAQUETTES INTERACTIVES, pas sur cette prose** — attendu : une maquette par forme décrite dans « La forme de l'écran » ci-dessous, qui fait jouer d'abord les gestes fréquents de chaque rôle (« Les gestes que la maquette fait jouer d'abord »), sur les mêmes données de décor (un administrateur, un propriétaire, un groupe d'étudiants de douze comptes, un login partagé, un compte jamais venu, une collection sans propriétaire), à 1 280 px et à 375 px, en thème sombre et clair ; la forme retenue est nommée ici avec sa raison. Les croquis de cette fiche disent ce que chaque forme range où ; ils ne disent pas ce qu'on éprouve en la regardant, et c'est ce que la demande juge — **tranché par Hugo le 2026-09-16, sur les maquettes : la FORME 1, une liste et une fiche, côte à côte.** Ses mots : « Liste et fiches, c'est parfait. Harmonieux, bien rangé, visuellement agréable et ordonné. » Les maquettes sont une publication privée de la coordination, hors du dépôt. Les formes 2 et 3 restent décrites dans « La forme de l'écran », comme trace de l'option écartée. **Offert par la maquette, non jugé** — le verdict porte sur la forme 1 seule, sans mention de largeur, de thème ni de modèle de droits : les largeurs 375, 768 et 1 280 px (à 375, une colonne, la fiche en plein écran sous « ← Liste », l'axe en liste déroulante, et « Qui entre » en CARTES, une par accès ; à 768, deux colonnes, la liste plus étroite, les libellés de navigation masqués) ; les thèmes sombre et clair, sur les couleurs de `static/style.css` ; les trois issues d'`AUTH-10` sur le même gabarit ; les deux options de la décision 2. Rien de cela n'est tranché par cette case
- [ ] **Les listes se trient par NOM ou par RÉCENCE** — demandé par Hugo le 2026-09-16 en retenant la forme 1 : « Il manque seulement un mode de tri je pense (date et alphabet peut-être ?) ». Ce que la seconde version de la maquette en a fait, repris comme attendu : **« A → Z »** sur le nom LU — le nom lisible d'une personne, à défaut son login ; le nom d'un groupe ou d'une collection ; **« Récents d'abord »** par date — la dernière venue pour une personne, la dernière venue d'un de ses membres pour un groupe, la dernière modification pour une collection ; ce qui n'a pas de date passe à la fin ; « À regarder » reste en tête, hors tri. Attendu : sur chacun des trois axes, les deux tris rendent l'ordre décrit, un objet sans date est en fin de liste, et le tri choisi survit au changement d'axe et à l'adresse. **Deux de ces dates n'existent pas encore, et la troisième est approchée** — la case ne se coche pas sans elles : (1) la dernière modification d'une COLLECTION n'est pas en base : `collection` ne porte qu'une `date_creation`, et modifier ses descripteurs n'écrit rien au journal — c'est le défaut « Modifier une collection ne laisse aucune trace » qui la rendrait lisible ; ranger ou sortir un album n'y écrit rien non plus, et la définition de « modification » devra dire si cela compte ; (2) la dernière venue d'un membre suppose de connaître les MEMBRES d'un groupe, que l'application ne lit pas aujourd'hui — la lecture de l'annuaire d'`AUTH-6` ; (3) la dernière venue d'une PERSONNE existe (`utilisateur.derniere_vue`), mais seulement pour qui est venu, et à l'heure près : elle n'est réécrite qu'une fois par heure par login. Un compte jamais venu n'a pas de date, et se range donc en fin de liste

### Mesurer, avant de construire
- [x] **L'import en lot de la décision 5 (b) est mesuré** — attendu : sur la pile de recette, trente comptes FICTIFS créés en un seul geste par l'outil de LLDAP (fichier ou script), jamais les comptes qui portent le décor des passes ; la durée, les gestes et ce qu'il faut savoir sont écrits dans `docs/exploitation.md` ; un compte importé se connecte au portail, et les trente comptes sont retirés après la mesure — **mesuré le 2026-09-17** par la coordination, sur accord de Hugo pour l'identifiant d'administration de l'annuaire : `/app/bootstrap.sh` de l'image LLDAP 0.6.3, un fichier JSON par compte, trente comptes et un groupe en 8 secondes, code de retour 0 ; `essai07` accepté par le portail (`/api/firstfactor` 200), un mauvais mot de passe refusé (401) ; les trente comptes et le groupe supprimés, et la liste des comptes relue IDENTIQUE à celle d'avant. Le mot de passe d'administration ne sort jamais du conteneur. Écrit dans `docs/exploitation.md`, § « Importer une promotion en une fois », avec le piège `DO_CLEANUP=true` (qui supprimerait tout compte absent des fichiers) et la limite non mesurée : la remise des mots de passe initiaux
- [ ] **Le délai d'un RETRAIT de groupe est mesuré** — l'ajout l'est (entre 4 min 53 s et 5 min 52 s, recette, 2026-09-15, `AUTH-7`), le retrait jamais. Attendu : sur la pile de recette, un compte d'essai retiré de `annotateurs` perd l'accès à « esther v1 » au bout d'un délai noté ; et ce qui arrive à une session DÉJÀ ouverte. C'est le délai pendant lequel quelqu'un qu'on vient de retirer lit encore, et `docs/modele-et-droits.md` le dit « immédiat »
- [ ] **Le chemin vers les réglages du portail est constaté** — « Gérer les appareils » a été atteint depuis l'écran du code (recette, 2026-09-15). Attendu : l'adresse d'une page de réglages du portail, joignable directement par un compte connecté, notée ici ; c'est elle que le menu du compte proposera. Si elle n'existe pas, le menu renverra au seul « Mot de passe oublié ? », et c'est écrit

### Défauts trouvés en lisant — indépendants des décisions
- [x] **Une collection créée par un administrateur n'a AUCUN propriétaire, et l'écran lui dit le contraire** — `create_collection` n'inscrit de propriétaire que pour un compte qui n'est pas administrateur, et la Bibliothèque affiche à tous « « X » créée — vous en êtes propriétaire ». `CLAUDE.md` dit « zéro propriétaire » interdit en base ; seuls le RETRAIT et la RÉTROGRADATION du dernier propriétaire sont refusés. Attendu : le message dit vrai pour un administrateur, et la règle est soit tenue à la création, soit écrite comme limite. **Tranché par Hugo le 2026-09-16 : option B.** La collection reste sans propriétaire, la décision d'AUTH-3 et son test tiennent, rien ne change côté serveur. Le message de création ne dit « vous en êtes propriétaire » que si la réponse du serveur le montre ; à un administrateur, il dit qu'il administre la collection sans en être propriétaire, et où lui en désigner un. L'option A — l'administrateur propriétaire de ce qu'il crée — a été écartée parce qu'elle renversait une décision pesée par AUTH-3, et laissait une ligne de propriété à retirer dans chaque collection créée pour quelqu'un d'autre. La phrase « zéro propriétaire interdit en base », fausse telle qu'écrite (une collection peut NAÎTRE sans propriétaire : administrateur, mono-poste, outil en ligne de commande sans `--proprietaire`), est corrigée par la coordination dans `CLAUDE.md` et `autorisation.py`, hors de cette fiche (`e0ef3c7`). **Fait le 2026-09-16, `f79cd81`** : le message de création ne dit « vous en êtes propriétaire » que si la liste d'accès renvoyée par le serveur le montre ; à un administrateur, qu'il administre sans posséder et où désigner un propriétaire ; en mono-poste, où se règle qui entre. La liste vide ne promet plus la propriété à qui écrit partout. Éprouvé par `test_la_creation_ne_dit_proprietaire_qu_a_qui_l_est`, deux mutants tués — toujours propriétaire, jamais propriétaire —, chacun sur l'une des deux assertions. **La relecture a trouvé deux phrases de plus qui disaient le contraire** : la liste vide de l'Administration (« l'on en devient propriétaire »), corrigée par `abc3dc0` avec `test_une_liste_vide_ne_promet_la_propriete_qu_a_qui_la_recevra`, qui éprouve aussi celle de la Bibliothèque, restée sans test dans `f79cd81` — quatre mutants tués, une promesse faite à tort et une promesse tue à tort, sur chaque page ; et `docs/guide-utilisateur.md` (« il suffit d'être connecté, et l'on en devient propriétaire »), que la coordination corrige
- [x] **Modifier une collection ne laisse aucune trace** — `PATCH /api/collections/{id}` n'écrit rien au journal A3, alors que les accès (`lien`, `delien`), la création et la suppression y sont. Changer le référent, le régime de diffusion ou la base légale n'a donc ni auteur ni date. Attendu : un événement par modification, avec avant et après — **fait le 2026-09-16, `749ceb8`** : seuls les champs qui changent, sur la cible `collection`, retenue de toute sortie, ce qui garde le référent hors des artefacts (AUTH-4). Éprouvé par `test_modifier_une_collection_laisse_une_trace`, et le mutant « sans journal » tué. Le mutant « journaliser tous les champs » est tué lui aussi, joué sur une copie hors de l'arbre partagé
- [x] **La modale d'album propose des collections où l'on ne peut pas ranger** — `remplirCollections` liste toutes les collections LUES ; en choisir une qu'on ne fait que lire rend « Collection N introuvable ». Et sa note « l'album entrera dans une collection par défaut, créée à cette occasion » est fausse derrière le proxy pour qui n'est pas administrateur : la création rend un 403. Lu dans le code, pas joué. Attendu : la liste ne propose que les collections où l'on écrit, et la note dit ce qui arrivera — **fait le 2026-09-16, `f79cd81`**, par le moyen validé par Hugo : `GET /api/collections` renvoie `ecrivable`, sur le modèle d'`exportable`, et l'écran filtre la modale de création ET la liste « ranger dans une collection » de l'édition, qui avait le même défaut. Sans collection où écrire, la note annonce la collection de repli à qui écrit partout, un refus aux autres. Le filtre ne remplace aucune garde : `create_album`, `ranger_album` et `sortir_album` refusent déjà en 404, et `test_ranger_ailleurs_demande_d_ecrire_des_DEUX_cotes` l'épingle. Éprouvé par `test_la_liste_dit_ou_l_on_ecrit` (vu rouge avant le code ; deux mutants tués, `ecrivable` calculé comme « lire » et comme « administrer ») et `test_la_modale_d_album_ne_propose_que_ou_l_on_ecrit` (trois mutants tués, un par assertion : création sans filtre, appartenance sans filtre, note toujours « totale »)
- [x] **`tools/gerer_collections.py` défait ce que les routes gardent** — `retirer` et `supprimer` n'ont ni la garde « aucun album hors collection » (409 à l'écran) ni l'écriture au journal. Attendu : les mêmes gardes que les routes, ou la limite écrite dans l'aide de l'outil — **fait le 2026-09-16, `749ceb8`** : `retirer` et `supprimer` refusent de laisser un album sans collection ; `creer`, `modifier` et `supprimer` écrivent au journal ce que les routes y écrivent. Ranger et retirer un album n'écrivent rien, ni ici ni à l'écran, et l'aide de l'outil le dit. Cinq mutants tués (`test_l_outil_refuse_de_laisser_un_album_sans_collection`, `test_l_outil_ecrit_au_journal_ce_que_les_routes_y_ecrivent`)
- [ ] **La documentation d'usage ne décrit plus ce parcours** — `docs/guide-utilisateur.md` renvoie « Créer un compte, un groupe » au fichier des comptes du portail, qui n'est plus que le repli ; `docs/modele-et-droits.md` dit qu'un retrait de groupe ferme la porte « immédiatement » ; `docs/hebergement-securite.md` range encore l'octroi d'accès dans la Bibliothèque ; aucun document ne dit qu'un compte doit être dans `lldap_admin` pour créer des comptes, ni que « Mot de passe oublié ? » échoue pour ces comptes ; aucun ne décrit le départ d'une personne comme une suite ordonnée de gestes. Attendu : les deux documents d'usage décrivent le parcours tel qu'il sera après les décisions ci-dessus — c'est pourquoi cette case attend, plutôt que de corriger aujourd'hui un texte qui changera

## L'ordre de construction — 2026-09-17

Validé par Hugo. Chaque étape nomme le chantier qui la porte ; cette fiche ne recopie pas
leurs cases.

1. **Lire l'annuaire** — `AUTH-6`, case « L'application LIT l'annuaire ». C'est le
   préalable de tout le reste : la liste de choix de la décision 4, les membres d'un groupe,
   le tri « Récents d'abord » d'un groupe, et les signaux « groupe disparu » et « jamais
   venu ». Une lecture impossible dit « je n'ai pas pu vérifier » et ne bloque rien.
2. **Le bloc « 👥 Comptes et groupes » de l'Administration** — cette fiche, avec `AUTH-7`
   pour la vue des comptes qu'il remplace. Forme liste et fiche, axes Comptes, Groupes et
   Collections, tri par nom ou par récence, « À regarder » en tête. Le lexique de la
   décision 7 s'y applique dès le premier écran.
3. **Les accès dans la fiche de la collection** — la frontière que `COL-2` porte depuis son
   renvoi du 2026-09-17, avec `UX-4` pour le tableau devenu cartes sous 768 px, et la liste
   de la décision 4 et ses trois textes. L'écran ne connaît aucun niveau en dur : ce qu'`AUTH-10`
   décidera s'y logera sans le refaire.
4. **Le référent de l'instance affiché aux administrateurs** — une ligne de lecture, en
   dernier (décision 6).

**Hors de cet ordre**, parce qu'ils n'en dépendent pas : « Mon compte » (`AUTH-9`), qui
s'ouvre par le menu du compte déjà livré ; l'import d'une promotion, documenté
(`docs/exploitation.md`) ; et la date de dernière modification d'une collection, que le
journal écrit depuis `749ceb8`.

## Le parcours actuel, geste par geste — 2026-09-16

Écrit comme on le vit. Sources : les passes de QA jouées (`annuaire-recette`,
`repli-annuaire`, `totp-appareil-perdu`, `compte-collectif`, `bandeau-portee-vide`,
`collections-bibliotheque`), les fiches `AUTH-6`, `AUTH-7`, `AUTH-9`, `AUTH-10`, `INFRA-8`,
`UX-4`, `UX-10`, `COL-2`, les trois documents d'exploitation, et le code de `dev` lu le
même jour. Ce qui y est dit **mesuré** l'a été ; le reste est lu.

**Où vit chaque geste**

| Geste | Où | Qui |
|---|---|---|
| Créer un compte | interface de LLDAP, après le portail ET une seconde connexion | un administrateur, qui doit aussi être `lldap_admin` |
| Le ranger dans un groupe | interface de LLDAP | idem |
| Première connexion, mot de passe | portail Authelia, « Mot de passe oublié ? » | la personne |
| Second facteur | portail Authelia | la personne, si `bd-admins` |
| Créer et décrire une collection, son référent | Bibliothèque → 📚 Collections | toute identité crée ; le propriétaire décrit |
| Faire entrer quelqu'un dans une collection | Administration → 👥 Accès aux collections | le propriétaire, ou un administrateur |
| Déclarer un login partagé | Administration → 👤 Comptes vus | un administrateur, après la première venue du compte |
| Référent de l'instance | `.env` sur le serveur, en SSH | l'administrateur système |
| Désactiver | nulle part : LLDAP ne sait pas, la règle `archives` n'est pas construite | — |
| Supprimer un compte | interface de LLDAP, verdict lu dans 👤 Comptes vus | un `lldap_admin` |
| Nettoyer un second facteur orphelin | console du serveur | l'administrateur système |

Cinq lieux, dont deux derrière une connexion supplémentaire, et un nom — celui du groupe —
qu'on tape deux fois : une fois dans l'annuaire pour le créer, une fois dans l'application
pour lui ouvrir une collection, sans que la seconde vérifie la première.

### 1. Créer la personne

L'administratrice ouvre l'adresse de l'annuaire. Le portail lui demande son mot de passe
et son code — l'annuaire est réservé à `bd-admins`, en second facteur. Puis la page de
LLDAP lui demande de se connecter une seconde fois. Elle remplit un formulaire : login, nom,
courriel, mot de passe. Elle ne transmet pas ce mot de passe : l'arrivant posera le sien.

**Ce qui rate sans bruit.** Son compte doit être dans `lldap_admin` pour créer, ce
qu'aucun document de `docs/` ne dit, et ce rôle permet aussi de supprimer. Le fichier de
repli n'est pas mis à jour : le jour où il servira, il authentifiera moins de monde, et ça
ressemblera à un succès (mesuré le 2026-09-10). Recréer un login déjà utilisé rend au
nouvel arrivant les accès de l'ancien, lui fait hériter de sa date d'arrivée, et fusionne
les deux personnes dans la provenance. Trente arrivants font trente formulaires.

### 2. La ranger dans un groupe

Dans la même interface, elle ajoute le compte au groupe du cours. L'effet arrive entre 4 et
6 minutes plus tard, sans reconnexion (mesuré le 2026-09-15) : c'est Authelia qui relit
l'annuaire, pas l'application.

**Ce qui rate sans bruit.** Rien n'empêche deux groupes à la fois : le modèle décidé
(`AUTH-6`) en veut un seul, le code CUMULE les niveaux de tous les groupes — plus permissif
que le modèle, et muet. Un compte sans aucun groupe ne reçoit pas du tout l'en-tête des
groupes (mesuré le 2026-09-09) : ce n'est pas une panne, mais c'est indiscernable d'une
panne pour qui lit le bandeau technique.

### 3. La première connexion

L'arrivant reçoit un message : son login et l'adresse de l'APPLICATION. Sur le portail, il
clique « Mot de passe oublié ? », reçoit un lien par courriel valable 15 minutes, choisit
son mot de passe, puis ouvre l'application. Un membre de `bd-admins` enregistre en plus un
appareil : le portail lui envoie un code à huit caractères.

**Ce qui rate sans bruit.** Ramené au portail sans destination après « Mot de passe
oublié ? », il verrait « Enregistrez votre premier appareil » même avec un compte à mot de
passe seul, et croirait l'inscription ratée ; seule la phrase du message d'accueil l'en
détourne. C'est lu dans le code d'Authelia et accepté par l'équipe, pas encore mesuré
(`INFRA-7`, où la case qui le mesurerait est ouverte). Un courriel qui ne part pas
ne se voit que dans les journaux d'Authelia, en SSH. « Mot de passe oublié ? » échoue pour un
compte `lldap_admin` (mesuré le 2026-09-11) — c'est-à-dire pour les administrateurs, ceux
qui détiennent le recours.

### 4. Ce qu'il voit en arrivant

Une application vide et un bandeau replié : « Aucune collection ne vous est ouverte. »
Déplié, il nomme le référent de l'instance. Ses groupes ne sont lisibles que dans
l'infobulle de son nom, en haut à droite, et nulle part au toucher. Il n'a aucun endroit où
lire ce que l'application sait de lui (`AUTH-9`, rien de commencé).

**Ce qui rate sans bruit.** Sans référent posé dans `.env`, le bandeau ne nomme personne.
Un compte en lecture seule voit un écran d'annotation ouvert et reçoit un refus au premier
geste : le navigateur ne sait pas qu'il n'écrit pas. Et côté administration, ce compte
n'existe pas encore : il n'apparaîtra dans 👤 Comptes vus qu'après sa première page.

### 5. Créer et décrire la collection

Le propriétaire — un enseignant, qui n'administre rien — crée sa collection dans la
Bibliothèque, la décrit, pose son référent. Le message qui suit lui dit où faire entrer
quelqu'un : un autre écran.

**Ce qui rate sans bruit.** Créée par un administrateur, la collection n'a aucun
propriétaire, et l'écran lui dit le contraire. Changer le référent ou le régime de diffusion
ne laisse aucune trace au journal. Les responsables scientifiques, eux, ne s'écrivent qu'en
ligne de commande.

### 6. Faire entrer quelqu'un

Dans l'Administration, il déplie sa collection, tape un nom dans un champ libre — un login
ou un nom de groupe —, choisit si c'est un utilisateur ou un groupe (obligatoire depuis
`1677c67`), un niveau, et s'il peut exporter.

**Ce qui rate sans bruit.** Un nom de groupe mal tapé n'ouvre rien et n'est jamais signalé.
Un login jamais venu est signalé, mais une faute de frappe et un arrivant pas encore venu
disent la même chose. Un groupe renommé ou supprimé dans LLDAP laisse un accès mort que rien
ne relie à rien (`AUTH-6`, bloqué derrière la lecture de l'annuaire). Le niveau
« écriture » permet aussi de supprimer un album, sans retour par Ctrl+Z (`AUTH-10`, rien
d'engagé). Le 2026-09-16, pendant la remise en état d'une passe, deux groupes sur deux ont
d'abord été accordés comme des utilisateurs.

### 7. Déclarer un compte partagé

Un groupe d'étudiants travaille sous un login commun. L'administrateur l'ouvre dans
👤 Comptes vus et le passe en « Collectif (login partagé) » : l'accord inter-annotateurs le
met à part, les exports le nomment `collectif-N`, Ctrl+Z n'y remonte que cinq minutes.

**Ce qui rate sans bruit.** Non déclaré, il est lu comme une personne, et rien ne le
devine. Le geste n'est possible qu'après sa première venue, et se refait pour chaque
nouveau login partagé.

### 8. Un mot de passe ou un téléphone perdus

La personne clique « Mot de passe oublié ? ». Un administrateur qui a perdu son téléphone
passe par « Gérer les appareils » depuis l'écran du code, reçoit un code par le notifier et
enregistre un nouvel appareil (mesuré en recette le 2026-09-15, sans le courriel).

**Ce qui rate sans bruit.** Qui détient le mot de passe d'un administrateur ET sa boîte
aux lettres peut remplacer son second facteur (décision ouverte dans `AUTH-7`). Un mot de
passe changé dans LLDAP ne change pas le fichier de repli, qui réadmettrait l'ancien.

### 9. Le départ

Il n'y a pas de procédure. Les gestes existent, épars : retirer les accès nominatifs
(Administration), retirer du groupe (LLDAP, avec un délai jamais mesuré), désactiver
(impossible dans LLDAP ; la règle `archives` est conçue dans `AUTH-7` et absente de la
configuration), supprimer (LLDAP, en lisant avant le verdict de 👤 Comptes vus).

**Ce qui rate sans bruit.** Une suppression laisse quatre orphelins (`AUTH-7`) : ses accès,
qu'un login recréé retrouverait ; ses actes au journal, qu'on ne doit pas nettoyer ; son
second facteur chez Authelia, nettoyable en console seulement ; sa ligne miroir. La dernière
propriétaire supprimée hors de l'application laisse un propriétaire fantôme que seul un
administrateur remplace, et aucune liste ne montre ces collections (`AUTH-6`). Si elle était
référente, rien ne le rappelle.

## Le parcours visé

**Un point d'entrée par rôle, et non par outil.** La complexité ne vient pas du nombre
d'outils — l'application n'authentifie personne et ne doit pas s'y mettre (`AUTH-1`) — mais
de ce que chacun doit SAVOIR lequel ouvrir, et de ce que l'application ne sait rien de
l'annuaire : elle fait taper des noms qu'elle ne peut pas vérifier.

**La personne** ouvre le menu de son nom (`UX-14`, en cours : « Déconnexion » y entre, à
toutes les largeurs). Elle y trouve **Mon compte** (`AUTH-9`) : qui l'application croit
qu'elle est, ses groupes en clair, les collections qu'elle lit, écrit ou possède, NOMMÉES,
et à qui écrire. Deux liens sortent vers le portail : changer son mot de passe, gérer ses
appareils. L'application n'y écrit rien.

**Le propriétaire** reste dans sa collection : la décrire et y faire entrer quelqu'un au
même endroit (décision 2 ci-dessus, si (b)). Il CHOISIT les groupes et les comptes dans une
liste lue dans l'annuaire, groupes d'abord ; ce qu'il tape hors de la liste est dit
« inconnu de l'annuaire ». Les accès se lisent en tableau (`UX-4`), et en ACTES plutôt qu'en
noms de niveau dès le modèle d'aujourd'hui : ce que le serveur accorde ensemble est dessiné
lié, et la décision d'`AUTH-10` ne fera que délier (section « La finesse des droits »).

**L'administrateur** a une vue des personnes et des groupes : TOUS les comptes de l'annuaire,
qu'ils soient venus ou non ; pour chacun, ses groupes, ses collections, sa nature, sa
dernière venue, et le verdict qui décide d'une suppression. Pour chaque groupe, ses membres
et ses collections. Les signaux qui manquent aujourd'hui y vivent : l'accès donné à un
groupe qui n'existe plus, la collection sans propriétaire vivant (`AUTH-6`), le login
partagé pas encore déclaré. Tout ce qui MODIFIE un compte renvoie à l'annuaire par un lien
qui ouvre la bonne fiche (décision 1, si (A)). Le départ s'y lit comme une suite ordonnée —
retirer, archiver, supprimer seulement si rien ne serait orphelin.

**L'administrateur système** ne garde que ce qui relève du serveur : la politique d'accès
d'Authelia, l'éventuel import d'une promotion (décision 5), les recours en console.

### Ce qui fait le passage, dans l'ordre

1. **Les défauts de la zone « Défauts trouvés en lisant »** — aucun ne dépend d'une décision.
2. **La lecture de l'annuaire** — la case d'`AUTH-6` « L'application LIT l'annuaire »,
   décidée le 2026-09-09, clé de voûte de tout ce qui suit. Elle entraîne ailleurs ce
   qu'`AUTH-6` a écrit : de nouvelles sorties à déclarer au cliquet d'`AUTH-5`, et la
   distinction entre LIRE pour composer et AUTHENTIFIER, qui n'existe encore nulle part par
   écrit.
3. **Les maquettes interactives** — la forme se choisit AVANT de construire les étapes 4 à
   6, et les maquettes jouent aussi les issues d'`AUTH-10` sur l'écran d'attribution
   (zones « La forme de l'écran » et « La finesse des droits »). **La forme est tranchée le
   2026-09-16 : la forme 1.** Reste à jouer les issues d'`AUTH-10` sur l'écran
   d'attribution.
4. **La vue des personnes et des groupes** — décisions 1, 3, 6 et 7.
5. **Le choix dans l'annuaire, la place des accès, et les accès en actes** — décisions 2 et
   4, dans le même geste que la refonte en tableau d'`UX-4`. `AUTH-10` peut trancher avant,
   pendant ou après : l'écran est fait pour ne pas avoir à le savoir.
6. **Mon compte** — `AUTH-9`, par le menu d'`UX-14`.
7. **Le départ** — la règle `archives` d'`AUTH-7`, éprouvée, et la suite ordonnée dans la vue.
8. **La documentation d'usage** — réécrite sur le parcours obtenu.

## La finesse des droits — ce que l'écran d'attribution doit pouvoir montrer

Demandé par Hugo le 2026-09-16, en validant cette fiche : *« si on va dans la finesse des
différentes opérations, comme on en avait discuté »*. La discussion est `AUTH-10`, relue en
entier le même jour. **Aucune de ses décisions n'est prise ici** : elles restent les siennes
— trancher entre les remèdes C, B et A, ajouter ou non un niveau, écrire le périmètre de
`contribution` route par route. Ce que cette section fixe, c'est la forme d'un écran qui
supporte toutes les issues.

**Les opérations, par famille** — celles d'`AUTH-10`, mesurées sur les 73 routes qui
écrivent, séparées par ce qui se DÉFAIT et non par l'objet, plus les deux capacités qui
existent déjà hors de l'échelle.

| Opération, dite en actes | Se défait ? | Accordée aujourd'hui par | Ce qu'`AUTH-10` pourrait changer |
|---|---|---|---|
| **Lire** la collection | — | `lecture` | rien |
| **Annoter** : régions, transcription, note, tags posés, locuteurs, tokens | oui par Ctrl+Z, sauf les tokens et la validation grammaticale | `ecriture` | séparée du reste par `contribution` (remède B) ; les deux exceptions réversibles par le remède A |
| **Structurer** le corpus : importer, réordonner, supprimer planches et albums | non ; supprimer un album efface ses masters sans rien écrire au journal | `ecriture` | une trace et un sursis (remède C), sans toucher aux droits |
| **Gérer le vocabulaire** : créer, renommer, fusionner domaines, dimensions, valeurs, tags, personnages | non, et déborde la collection | `ecriture` | la meilleure candidate à une case hors rang, selon `AUTH-10` |
| **Lancer des lots** et des passes | sans perte, mais bloque les autres | `ecriture` | exclue de `contribution`, si le niveau est fait |
| **Exporter** | — | la case « peut exporter » (`DROIT-2`), d'office au propriétaire | rien : c'est le gabarit hors rang déjà construit |
| **Décider qui entre** | les changements d'accès sont tracés, non annulables | `proprietaire` | rien |

Hors de ce tableau, et hors de toute collection : **l'administrateur d'instance**
(`bd-admins`), qui court-circuite les accès (`AUTH-4`). L'écran le déclare, il ne l'accorde
pas.

**Comment le parcours visé les présente.** Chaque accès se lit comme une ligne d'ACTES,
jamais comme un nom de niveau — c'est la case d'`AUTH-10` « l'interface se rend en cases à
cocher, acquis quel que soit le modèle », et cet écran est l'endroit où elle s'applique.
Ce qui s'ORDONNE se rend en échelle : cocher un cran coche ceux du dessous. Ce qui ne
s'ordonne pas se rend en case À CÔTÉ, comme « peut exporter » aujourd'hui. Et ce que le
modèle rend INSÉPARABLE est dessiné lié — une seule accolade, un seul geste —, au lieu
d'être caché sous le mot « écriture ».

```
 Collection Test — qui entre
                          lire  annoter  structurer  vocabulaire  lots  │ exporter │ décider
 👥 etudiants-bd-2026      ■    ■────────■───────────■───────────■      │    □     │   □
 👥 annotateurs            ■    □        □           □           □      │    ■     │   □
 👤 proprio                ■    ■────────■───────────■───────────■      │    ■     │   ■
                               └──── inséparables aujourd'hui ─────┘
 ⚠ supprimer un album efface ses images et ne se rattrape pas
```

Le même croquis sous `contribution` : « annoter » se détache de la barre, et la ligne des
étudiants peut porter ■ □ □ □. Sous une case hors rang pour le vocabulaire : la colonne
passe à droite du trait vertical. Le gabarit ne bouge pas — c'est la case « Les maquettes
tiennent les issues d'`AUTH-10` ».

**Ce que la présentation doit éviter, et `AUTH-10` l'a écrit d'avance.** Sa section « Ce qui
rouvrira la question » nomme le risque d'un écran « qui se mettrait à énumérer des ACTES
sans que la décision de modèle ait été prise ». Le risque est réel si les colonnes se
cochent SÉPARÉMENT alors que le serveur les accorde ensemble : l'écran promettrait une
finesse qui n'existe pas, et un refus viendrait le démentir. D'où les liaisons dessinées :
énumérer les actes en disant lesquels vont ensemble, c'est dire le modèle actuel en clair,
pas le devancer.

**Ce qui ne dépend PAS d'`AUTH-10`**, et peut se faire avec les trois niveaux d'aujourd'hui :
les libellés en actes ; les liaisons dessinées ; « exporter » et « décider qui entre » en
cases à part ; la description des actes servie par le serveur ; l'avertissement sur la
suppression, tant qu'elle ne se rattrape pas ; « Mon compte » qui dit ce qu'on peut faire.

**Ce qui en DÉPEND** : qu'« annoter » se détache (remède B, et le périmètre de
`contribution` écrit route par route) ; qu'une colonne passe hors rang ; que l'avertissement
change (remède C) ; que le refus d'écrire devienne un 403 nommé plutôt qu'un 404 sur un
objet qu'on voit (le « trou d'affichage » d'`AUTH-10`, qui touche aussi ce qu'un écran peut
dire après coup).

**L'ordre entre les deux fiches.**

1. `AUTH-12` construit l'écran d'attribution en actes, sur le modèle d'aujourd'hui. Rien
   n'y attend `AUTH-10`.
2. `AUTH-10` tranche quand l'équipe le décide. Si c'est B ou une case hors rang, ce qui
   change est la description des actes, le modèle et le cliquet ; l'écran montre une
   liaison de moins ou une case de plus.
3. **Le moment de trancher `AUTH-10` est écrit dans `AUTH-10` lui-même**, et ce chantier
   s'en approche : sa décision de ne rien engager deviendrait « intenable » à un premier
   incident, ou à « l'arrivée d'une promotion de trente personnes » — c'est-à-dire le
   scénario même de la décision 5 ci-dessus. Aucune décision n'est prise ici ; le fait est
   noté pour que la rentrée ne le découvre pas. Le remède C, lui, ne croise aucun écran et
   reste disponible à tout moment.

## La forme de l'écran

Demandé par Hugo le 2026-09-16 : *« la question esthétique va être importante. Le côté
monolithe qui se déroule sans grande esthétique, je ne suis pas certain que ce soit la bonne
direction. »* Il vise les panneaux d'aujourd'hui : l'Administration, quatre blocs posés l'un
sous l'autre par quatre chantiers différents (`UX-4` l'a constaté le 2026-09-08), et les
Collections de la Bibliothèque, où chaque collection se déplie en un formulaire long suivi
de son export.

**Tranché le 2026-09-16, sur les maquettes : la forme 1**, une liste et une fiche côte à
côte — « Liste et fiches, c'est parfait. Harmonieux, bien rangé, visuellement agréable et
ordonné. » Hugo y a demandé un tri, par nom et par date (case « Les listes se trient par NOM
ou par RÉCENCE »). **Les formes 2 et 3 restent décrites ci-dessous, comme trace de l'option
écartée**, avec leurs coûts et leurs risques : c'est ce qu'on relira si la forme 1 se
révèle mal tenir un usage qu'on n'a pas maquetté.

**La forme s'est choisie sur des MAQUETTES INTERACTIVES**, construites à partir de cette
section, et non sur la prose (case « La forme se choisit sur des maquettes », zone « La
forme de l'écran »). Ce qui suit est écrit pour qu'on puisse les construire sans deviner :
ce qu'on voit d'emblée, comment on passe d'un objet à l'autre, où vit chaque geste, et ce
que devient chaque forme à 375 px.

### Ce qui est commun aux trois formes

**Le cadre ne change pas.** La bande 1 garde la navigation des cinq surfaces et, à droite,
la pastille du compte, qui ouvre le menu d'`UX-14` : **Déconnexion**, et **Mon compte**
quand `AUTH-9` existera. La
bande 2 porte les outils de la page. La forme ne décide que du corps.

**Trois objets, et la même FICHE pour chacun, quelle que soit la forme.**

- **La fiche d'une personne** (un compte) — en tête : login, nom, nature (« une personne »
  / « login partagé », sélecteur pour l'administrateur), dernière venue, et un signal s'il y
  en a un (« jamais venue », « partagé ? »). Puis **Groupes** : des pastilles, et « Modifier
  dans l'annuaire ↗ ». Puis **Collections** : une ligne par collection, avec les actes
  ouverts (en lecture seule ici ; chaque ligne mène à la fiche de la collection). Puis
  **Départ**, REPLIÉ : le verdict (« rien à orpheliner » ou « laisse N actes, M accès ») et
  les étapes dans l'ordre — retirer ses accès nominatifs, l'archiver, la supprimer seulement
  si rien ne serait orphelin.
- **La fiche d'un groupe** — en tête : nom, « défini dans l'annuaire ↗ », nombre de
  comptes. Puis **Collections ouvertes** à ce groupe, avec les actes. Puis **Membres**, pour
  l'administrateur seulement. Puis « Ouvrir une collection à ce groupe… », qui mène à la
  fiche de la collection choisie, le groupe déjà sélectionné dans « Qui entre ».
- **La fiche d'une collection** — en tête : nom, nombre d'albums, régime de diffusion, et
  un signal (« sans propriétaire »). Puis **Qui entre** : le tableau d'accès en actes de la
  section « La finesse des droits », et sous lui la ligne d'ajout, qui CHOISIT un groupe ou
  un compte dans l'annuaire. Selon la décision 2, les autres parties — **Description**,
  **Diffusion**, **Référent**, **Exports** — sont dans la même fiche, dans la Bibliothèque
  (b), ou restent dans la Bibliothèque derrière un lien « Décrire dans la Bibliothèque ↗ »
  (a).

**Qui voit quoi**, et c'est la même règle dans les trois formes, bloc par bloc (`UX-10`) :
- l'**administrateur** a les trois axes — personnes, groupes, collections — et les signaux ;
- le **propriétaire** n'a que SES collections, et sur elles tous les gestes de « Qui entre ».
  Il ne voit pas les membres d'un groupe : la composition d'équipes qui ne sont pas la sienne
  lui reste cachée (`UX-4`, décision du 2026-09-13 ; toute exception se déclare à `AUTH-5`) ;
- **la personne** n'entre pas dans cet espace : elle a « Mon compte », qui est SA fiche de
  personne sans les gestes d'administration.

**Les signaux se regroupent sous « À regarder »** — accès donné à un groupe qui n'existe
plus, collection sans propriétaire, login partagé non déclaré, compte jamais venu. Chaque
signal mène à la fiche concernée.

### Les gestes que la maquette fait jouer d'abord

Les deux ou trois gestes les plus fréquents de chaque rôle, dans l'ordre où ils reviennent.

| Rôle | Geste | Fréquence |
|---|---|---|
| **Personne** | Lire ce qu'elle peut faire et à qui demander (Mon compte) | à l'arrivée, puis quand quelque chose lui est refusé |
| | Se déconnecter (menu du compte) | chaque séance |
| | Changer son mot de passe (lien vers le portail) | rare |
| **Propriétaire** | Faire entrer un groupe dans sa collection, et cocher ses actes | chaque cours |
| | Changer les actes d'un accès (passer un groupe en lecture en fin de semestre) | chaque cours |
| | Retirer un accès | fin de cours |
| **Administrateur** | Répondre à « je ne vois rien » : ouvrir la fiche de la personne, lire groupes, collections, venue | le plus fréquent en période d'arrivées |
| | Arrivée d'un cours : créer le groupe et les comptes (annuaire ↗), puis vérifier qu'ils sont venus et ont accès | chaque rentrée, par pics de trente |
| | Départ : lire le verdict, archiver ou supprimer ; déclarer un login partagé | fin de cours ; à la première venue d'un login partagé |

L'**administrateur système** n'a pas de geste fréquent ici : import de promotion (décision
5), recours en console. Il est hors des maquettes.

### Forme 1 — une liste et une fiche, côte à côte (RETENUE le 2026-09-16)

**D'emblée.** Deux colonnes. À gauche, un sélecteur d'axe — *Personnes · Groupes ·
Collections* —, un champ de filtre, un tri — *A → Z · Récents d'abord* —, puis la liste : le groupe « ⚠ À regarder (N) » DÉPLIÉ en
tête, puis les autres objets par ordre alphabétique, une ligne chacun (nom, et un état court :
« venue 14/09 », « jamais venue », « 12 comptes »). À droite, tant que rien n'est choisi, le
détail de « À regarder » ; une fois un objet choisi, sa fiche. Le propriétaire n'a pas de
sélecteur d'axe : la colonne de gauche liste ses collections.

```
┌ Comptes ──────────────────────────────────────────────────────────────┐
│ ( Personnes )  Groupes   Collections                    🔍 filtrer…    │
├───────────────────────────┬───────────────────────────────────────────┤
│ ▾ ⚠ À regarder (2)        │ alice — Alice Martin      [une personne ▾] │
│     carole   partagée ?   │ Dernière venue 14/09                       │
│     bob      jamais venu  │ Groupes   (annotateurs)  Modifier ↗         │
│ ▸ alice        venue 14/09│ Collections                                │
│   dora         venue 02/09│   Collection Test   lire annoter…  export  │
│   …                       │   Étude B           lire                   │
│                           │ ▸ Départ — rien à orpheliner               │
└───────────────────────────┴───────────────────────────────────────────┘
```

**Passer d'un objet à l'autre.** Cliquer une ligne de la liste remplace la fiche. Dans une
fiche, un nom de groupe ou de collection est un lien : il bascule l'axe et sélectionne
l'objet — la liste suit. L'adresse garde l'axe et la sélection (`?groupe=etudiants-bd`), pour
envoyer une fiche et pour que « Retour » du navigateur défasse le dernier saut.

**Où vivent les gestes.**
- *Créer une personne ou un groupe* : bouton « + Dans l'annuaire ↗ » en tête de la liste
  (décision 1 (A)) ; la personne apparaîtra dans la liste à sa lecture suivante.
- *Mettre dans un groupe* : fiche de la personne ou du groupe, « Modifier dans l'annuaire ↗ ».
- *Ouvrir une collection* : fiche de la collection, ligne d'ajout de « Qui entre » ; ou fiche
  du groupe, « Ouvrir une collection à ce groupe… ».
- *Cocher des droits* : fiche de la collection, tableau « Qui entre ».
- *Déclarer un login partagé* : en-tête de la fiche de la personne.
- *Partir* : fiche de la personne, partie « Départ ».
- *Se déconnecter* : menu du compte.

**À 375 px.** Une seule colonne à la fois : la liste occupe l'écran ; choisir un objet ouvre
sa fiche en plein écran, avec « ← Liste » en tête. Le sélecteur d'axe devient une liste
déroulante. C'est le motif de l'Atelier, dont l'arbre et le panneau latéral passent en
tiroirs sous le seuil (`UX-7`, piège à focus éprouvé). **Proposé par la maquette, non
jugé** : à 375 px, le tableau « Qui entre » devient une CARTE par accès, où les actes liés
forment UNE pastille (« annoter · structurer · vocabulaire · lots ») et où « exporter » et
« décider » sont des pastilles à part — une réponse possible à la question qu'`UX-4` a
laissée ouverte sur la ligne d'accès sous le seuil étroit. À 768 px : deux colonnes, la
liste plus étroite, les libellés de la navigation masqués.

**Coûte** : un gabarit à deux colonnes pour l'Administration, que seul l'Atelier a aujourd'hui ;
l'état dans l'adresse ; une liste parcourable au clavier. **Risque** : sur une tâche en
série — vérifier trente arrivants —, l'aller-retour entre liste et fiche fatigue à 375 px.

### Forme 2 — des onglets, un tableau par onglet, une ligne qui s'ouvre (écartée)

**D'emblée.** Une rangée d'onglets — *Personnes · Groupes · Collections · Instance* —, le
premier ouvert. Sous l'onglet, une barre de filtres dont une pastille « ⚠ À regarder (N) », puis
un tableau (`corpus-table`, comme la vue des comptes aujourd'hui) : une ligne par objet, des
colonnes (pour les personnes : login, nom, nature, dernière venue, collections, signal). Toutes
les lignes sont REPLIÉES. *Instance* reçoit la version servie et les moteurs. Le propriétaire
n'a qu'un onglet, *Mes collections* — donc pas de rangée d'onglets.

```
┌ Administration ───────────────────────────────────────────────────────┐
│  Personnes   ( Groupes )   Collections   Instance                      │
│  [⚠ À regarder (1)]  🔍 filtrer…                                        │
├───────────────────────────────────────────────────────────────────────┤
│ Groupe            Comptes   Collections                     Signal     │
│ annotateurs          4      Collection Test (lire)                     │
│ ▾ etudiants-bd      12      Collection Test (lire, annoter…)           │
│   │ Membres : alice, bob, … (12)          Modifier dans l'annuaire ↗   │
│   │ Ouvrir une collection à ce groupe…                                 │
│ ancien-cours         0      Étude B                    ⚠ n'existe plus │
└───────────────────────────────────────────────────────────────────────┘
```

**Passer d'un objet à l'autre.** Cliquer une ligne l'ouvre SOUS elle et referme celle qui
était ouverte : une seule fiche dépliée à la fois. Un lien vers un autre objet change
d'onglet, filtre le tableau sur cet objet et l'ouvre. L'adresse garde l'onglet et la ligne
ouverte.

**Où vivent les gestes.** Les mêmes que la forme 1, dans la ligne dépliée au lieu de la
colonne de droite ; « + Dans l'annuaire ↗ » à droite de la barre de filtres.

**À 375 px.** Les onglets deviennent une liste déroulante. Le tableau se lit comme aujourd'hui
dans son cadre défilant (`UX-7`), ou chaque ligne devient une carte — `UX-4` a laissé
ouverte exactement cette question pour le tableau des accès (« ce que la ligne d'accès
devient sous le seuil étroit est DÉCIDÉ ») ; la maquette la tranche pour les trois tableaux
à la fois.

**Coûte** : un composant d'onglets accessible, absent du dépôt — l'Exploration choisit sa vue
par une liste déroulante ; et la leçon d'`UX-10` : un bloc derrière un onglet fermé n'est
rendu par aucun audit, donc chaque audit devra ouvrir chaque onglet, et le déclarer.
**Risque** : comparer deux fiches est impossible, une seule étant ouverte.

### Forme 3 — un tableau de bord, et une page par objet (écartée)

**D'emblée.** Le tableau de bord de l'Administration : en tête, **À regarder**, les signaux
en liste, chacun un lien ; puis trois cartes — *Personnes (24)*, *Groupes (5)*, *Collections
(9)* —, chacune montrant ses cinq objets les plus récemment actifs et « Tout voir ». Pour le
propriétaire : *Mes collections*, et les seuls signaux qui les concernent.

```
┌ Administration ─────────────────────┐   ┌ Administration › Groupes ›        ┐
│ À regarder                          │   │ etudiants-bd-2026                  │
│  ⚠ Étude B n'a plus de propriétaire │   │ 12 comptes · défini dans           │
│  ⚠ 3 comptes jamais venus           │──▶│ l'annuaire ↗                       │
│  ⚠ carole : login partagé ?         │   │ Collections ouvertes               │
│ ┌ Personnes 24 ┐┌ Groupes 5 ┐┌ …    │   │   Collection Test  lire annoter…   │
│ │ alice  14/09 ││ etudiants ││      │   │ Membres  alice · bob · …           │
│ │ …  Tout voir ││ …         ││      │   │ Ouvrir une collection à ce groupe… │
└─────────────────────────────────────┘   └────────────────────────────────────┘
```

**Passer d'un objet à l'autre.** Chaque nom est un lien vers la page de l'objet ; un fil
d'Ariane en tête de page (*Administration › Groupes › etudiants-bd-2026*) ramène au
tableau de bord ou à la liste complète. « Tout voir » ouvre la liste d'un axe, filtrable.

**Où vivent les gestes.** Dans la page de l'objet, aux mêmes places que dans sa fiche ;
« + Dans l'annuaire ↗ » en tête de la liste « Tout voir » des personnes et des groupes. Le
propriétaire arrive depuis sa collection de la Bibliothèque DIRECTEMENT sur la page de
celle-ci.

**À 375 px.** La forme la plus naturelle : tout est déjà une colonne. Les trois cartes
s'empilent ; une page d'objet se lit de haut en bas.

**Coûte** selon la manière : des routes HTML neuves coûtent chacune les listes de surfaces
qu'`UX-10` a mesurées ; une seule page `/administration` qui change de vue selon son adresse
ne coûte qu'une route. **Risque** : une tâche en série fait aller et venir entre pages, et le
tableau de bord devient une étape de plus.

### Ce que les formes engagent ailleurs

- **« Mon compte » est la fiche de personne**, vue par la personne elle-même : mêmes faits,
  sans les gestes d'administration (`AUTH-9`, ouverte depuis le menu d'`UX-14`). Un seul
  composant évite deux écrans qui finiraient par se contredire.
- **La collection de la Bibliothèque suit la forme retenue** si la décision 2 retient (b) :
  description, diffusion, référent, qui entre et exports sont les parties d'UNE fiche, pas
  cinq blocs empilés.
- **`UX-4`** tient la cohérence : l'Exploration y sert de référence, et un même composant
  doit avoir la même apparence sur les cinq surfaces. La forme retenue ne doit pas inventer
  un sixième style, elle doit être celle qu'`UX-4` étend à l'Administration. Sa décision du
  2026-09-13 — les accès en TABLEAU, sans colonne d'identité, avec une colonne « Signal » —
  vaut dans n'importe laquelle des trois formes.
- **`UX-10`** a fait de l'Administration une page parce qu'« une vue, et les éléments dedans,
  décrit un lieu », et a posé que chaque bloc garde SA question d'autorisation. Les trois
  formes la respectent si chaque colonne, onglet ou page pose la sienne ; la forme 2 rend
  l'oubli le plus facile, un onglet regroupant.

## Ce qui est déjà ouvert ailleurs, et que cette fiche ne recopie pas

Chaque point garde sa case dans sa fiche ; les recopier ici compterait deux fois le même
travail. Les renvois vers AUTH-12 restent à poser chez eux, sur accord de la coordination —
cette fiche n'a été réservée qu'à elle-même.

- **`AUTH-6`** — l'application lit l'annuaire ; le groupe renommé ou supprimé ; la collection
  dont le propriétaire a perdu son groupe ; les logins partagés déclarés en production ; un
  stagiaire qui voit un corpus non vide.
- **`AUTH-7`** — désactiver sans supprimer (règle `deny`) ; le recours des administrateurs ;
  le repli qui perd des gens ; exiger le second facteur pour s'élever ; le TOTP orphelin d'un
  login qui revient ; les panneaux tiers.
- **`AUTH-9`** — modale ou page ; le panneau en mono-poste ; la portée nommée ; « changer mon
  mot de passe » n'entre pas dans l'application ; le crédit.
- **`AUTH-10`** — l'interface en cases qui énumèrent des actes ; aucun niveau engagé.
- **`UX-4`** — le panneau des accès en tableau, sa ligne d'ajout, son affichage étroit.
- **`UX-14`** — le menu du compte ouvert par la pastille.
- **`INFRA-7`** — la durée de session, et « Enregistrez votre premier appareil » au portail
  sans destination.

## Contexte

**Le chiffre qui décide n'est pas le total.** Jusqu'à 300 comptes en cinq ans, par pics de
trente, dont dix nommés au plus (`AUTH-6`, `AUTH-7`) : la douleur est la semaine de la
rentrée, et c'est elle que la décision 5 regarde.

**Ce que la lecture de l'annuaire ne change pas.** L'autorisation continue de ne lire que
l'en-tête des groupes, requête par requête ; l'application n'authentifie toujours personne ;
une panne de lecture ne ferme aucun accès (`AUTH-6`, attendus (a) à (c)). Ce qui entre est
une CONNAISSANCE, et un secret de service en lecture seule. La recommandation (A) de la
décision 1 s'arrête exactement là.

**Ce que la recette a montré le jour même.** La passe *Les collections dans la
Bibliothèque* a été jouée le 2026-09-16 : ses deux défauts — des messages loin du
geste, un genre par défaut qui a trompé deux fois sur deux — sont réparés dans `COL-2`. Ils
disent la même chose que la demande : l'écran faisait deviner.

**Trouvé en lisant, et déjà remonté** (hors de cette fiche) : la procédure de repli de
`docs/exploitation.md` vise des numéros de ligne que `dev` a décalés ; `verifier_deploiement.py`
contrôle `BD_AUTH_ADMIN_GROUPS` dans `.env` alors que le compose ne la transmet pas ; son
avertissement « référent manquant » compte les comptes du fichier de repli et non de
l'annuaire. La coordination les porte sur la liste d'avant la fusion de `dev` sur `main`.
