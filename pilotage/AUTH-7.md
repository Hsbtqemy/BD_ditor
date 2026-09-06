---
chantier: AUTH-7
statut: à venir
---

# AUTH-7 — administrer les comptes sans console

**Point de départ** — 2026-09-06, demandé en propres termes : *« pouvoir gérer la création
de compte sans passer par la console, surtout au lancement du produit. Et avoir une vue sur
tous les comptes actifs, pouvoir révoquer des droits ou supprimer directement un
utilisateur. »*

**Le critère d'acceptation, précisé le même jour** : *« tant qu'on peut avoir un panneau de
contrôle, où on peut activer, désactiver, créer, attribuer, potentiellement dans DEUX
ESPACES SÉPARÉS, ça me va. Tant qu'on évite la console. »*

Cela tranche une question que la fiche portait sans le dire : **il n'y a pas à unifier les
deux moitiés.** Attribuer un accès à une collection reste dans BDéditeur (panneau
👥 Collections, existant) ; créer, activer et désactiver un compte vit ailleurs. Deux
écrans, un seul critère — zéro console pour les gestes courants.

Conséquence sur la section « ce que BDéditeur pourrait apporter » plus bas : la vue de
l'usage (`premiere_vue`/`derniere_vue`) n'est PAS la demande. Elle reste un bonus utile —
voir qui s'est connecté et attend un droit —, elle ne conditionne aucun choix d'annuaire.

Aujourd'hui, créer un compte c'est : éditer `users_database.yml` en SSH, générer un hash
avec la CLI d'Authelia, contrôler le YAML, redémarrer le conteneur. Quatre gestes, sur le
serveur, dont un qui peut fermer l'instance à tout le monde s'il rate.

## Ce que la demande recouvre, et qui ne vit pas au même endroit

**Elle traverse deux systèmes**, et la moitié existe déjà. Le confondre ferait construire
deux fois ce qui est là.

| Geste demandé | Qui en est propriétaire | État |
|---|---|---|
| Créer un compte, mot de passe, second facteur | **Authelia** (`users_database.yml`) | SSH obligatoire |
| Voir les comptes existants | Authelia — et l'usage réel, `utilisateur` | aucun écran |
| Révoquer l'accès à une COLLECTION | **BDéditeur** (`collection_acces`) | panneau 👥 Collections, existe |
| Retirer quelqu'un d'un GROUPE | **Authelia** | SSH obligatoire |
| Supprimer un utilisateur | Authelia, **et des traces côté BDéditeur** | voir le piège ci-dessous |

« Révoquer des droits » désigne donc deux choses distinctes : l'accès à une collection se
retire déjà à l'écran ; l'appartenance à un groupe, non.

## Le piège que ni Authelia ni un annuaire ne verraient

**Supprimer un compte dans le système d'authentification laisse BDéditeur dans un état
qu'il s'interdit à lui-même.**

`collection_acces` référence un `principal` — un login ou un nom de groupe — et jamais une
appartenance ; c'est l'invariant d'AUTH-1, et il est délibéré. Conséquence : rien ne relie
la suppression d'un compte aux lignes qui le citent. Or `routes/collections.py` refuse par
un **409** qu'une collection se retrouve sans propriétaire, et cette garde ne s'exécute que
sur les opérations de l'application. Une suppression faite ailleurs — dans un annuaire, ou
à la main dans le YAML — passe à côté et produit exactement l'état interdit.

S'y ajoutent le journal de provenance (A3), qui cite l'agent et doit lui **survivre** — le
supprimer effacerait des chaînes de révision —, et la ligne `utilisateur`, simple miroir
d'affichage, qui deviendrait orpheline.

C'est le vrai contenu de ce chantier. L'écran est la partie facile.

## Le modèle proposé — 2026-09-06 : l'enseignant possède, l'étudiant passe

Posé par l'équipe, et il simplifie beaucoup : **le propriétaire d'une collection est
toujours l'ENSEIGNANT** — un compte stable —, tandis que les comptes ÉTUDIANTS tournent au
rythme des cours. Et pour ceux-là, non pas suppression mais **désactivation et archivage**.

Ce modèle est déjà servi par ce qui existe, sur les deux moitiés :

- **La désactivation est native.** Le backend fichier d'Authelia porte `disabled: false`
  par compte. Un compte désactivé ne se connecte plus, mais son login reste un principal
  valide : `collection_acces` garde son sens, le journal A3 continue d'attribuer, et rien
  ne devient orphelin. C'est exactement l'archivage demandé, sans rien construire.
- **Retirer l'accès d'un étudiant à la fin d'un cours ne détruit rien** — c'est un geste du
  panneau 👥 Collections, et `test_retirer_un_acces_ne_detruit_aucune_donnee` le prouve :
  l'album reste, le journal continue de le lui attribuer.
- **Le fantôme devient rare**, puisque le propriétaire est stable. Il ne disparaît pas
  pour autant : un enseignant part aussi, à l'échelle de quelques années, et la mesure
  ci-dessus reste le chemin de sortie.

**Deux limites, à connaître avant de choisir l'annuaire.**

BDéditeur **ne peut pas savoir qu'un compte est désactivé.** Il ne voit que des en-têtes,
et un compte désactivé cesse simplement d'apparaître. `utilisateur.derniere_vue` dira « ne
s'est pas connecté depuis six mois », jamais « archivé ». Les deux vues sont
complémentaires et aucune ne remplace l'autre : l'annuaire sait qui EXISTE, l'application
sait qui est VENU.

Et la désactivation est une propriété du backend, pas d'Authelia. Le fichier l'a ;
**rien ne garantit qu'un annuaire donné l'ait**, et la « supprimer » y remplacerait la
« désactiver ». C'est devenu un critère de choix, pas un détail d'implémentation.

## Trois chemins, et ce que chacun coûte

**1. Garder le fichier, documenter les gestes.** L'état actuel : `docs/exploitation.md`
porte la procédure, contrôle YAML compris. Coût nul, mais chaque arrivée passe par vous et
par un terminal — c'est précisément ce que la demande refuse.

**2. Un annuaire LDAP avec interface web** (LLDAP est le candidat pour une petite équipe).
Authelia passe du backend `file` au backend `ldap` ; la création de compte, les mots de
passe et les groupes se gèrent à l'écran. **BDéditeur n'y touche pas d'une ligne** :
l'application ne connaît que les en-têtes du proxy, et `collection_acces` stocke des NOMS
de groupes — un groupe LDAP `stagiaires` remplace le groupe fichier `stagiaires` sans que
rien ne s'en aperçoive. L'isolement d'AUTH-1 paie exactement ici. Coût : un service de plus
à faire tourner, sauvegarder et tenir à jour, et les comptes existants à recréer.

**3. Un outil d'administration écrit ici.** À écarter, sauf raison forte : il faudrait
manipuler des hashs de mots de passe, orchestrer un redémarrage d'Authelia, et surtout ce
serait un outil DISTINCT de BDéditeur — l'application n'authentifie personne (AUTH-1), et
lui confier la base d'authentification effondrerait le raisonnement de sécurité entier.
Écrire un gestionnaire de comptes est un métier ; LLDAP le fait déjà.

## Reste

### Trancher (la décision appartient à l'équipe)
- [x] Le rythme d'arrivée est cadré — **2026-09-06, par l'équipe** : le projet est aujourd'hui porté par un projet unique, mais il va s'ouvrir à d'autres personnes, avec des activités liées à certains COURS, donc des corpus très spécifiques et des groupes qui changent. Ce n'est plus « deux comptes stables ». Le motif redouté est nommé : *« on pourrait trop rapidement devoir gérer un SAV à l'aveugle »* — administrer sans voir. Cela déplace la balance vers le chemin 2, sans le trancher : c'est la case suivante
- [ ] **L'annuaire retenu sait DÉSACTIVER un compte sans le supprimer** — vérifié dans sa documentation ou sur une instance d'essai, pas supposé. Le backend fichier le fait (`disabled:`) ; c'est devenu un critère de choix depuis le modèle du 2026-09-06, puisque l'archivage en dépend. Un annuaire qui ne saurait que supprimer ferait perdre la distinction entre « parti » et « n'a jamais existé »
- [ ] Le chemin est choisi entre les trois ci-dessus, et la raison est écrite — y compris si c'est « on garde le fichier », qui est un choix légitime tant que le rythme reste faible

### Ce qu'il faut savoir AVANT de choisir (mesures, pas opinions)
- [ ] **Une version plus récente d'Authelia administre-t-elle les comptes ?** À vérifier AVANT d'ajouter un annuaire : cette instance tourne en 4.38.19, dont le portail ne gère que son propre second facteur et son propre mot de passe. Si une version ultérieure sait créer et désactiver un compte du backend fichier, le chemin 2 devient inutile — un service de moins à faire tourner, sauvegarder et tenir à jour. C'est la vérification la moins chère de cette fiche, et celle qui peut en annuler la moitié
- [x] Ce que devient une collection dont on supprime le dernier propriétaire **hors de l'application** — reproduit le 2026-09-06 (`test_un_proprietaire_disparu_laisse_une_collection_administrable_par_un_admin_seul`). **Ce n'est pas une impasse, mais elle exige un administrateur.** La ligne survit : la collection garde un propriétaire FANTÔME, qui ne peut plus se connecter. Un tiers ne voit rien (404). L'administrateur ne peut pas retirer le fantôme tel quel — le 409 « dernier propriétaire » l'en empêche, et il a raison. La seule sortie : désigner un remplaçant, PUIS retirer. Faisable entièrement à l'écran, sans SQL — mais impossible sans `bd-admins`
- [x] Ce que devient le journal A3 quand l'agent cité n'existe plus : **il survit**, et par construction. `activite.agent` est une colonne TEXTE sans clé étrangère, et rien ne joint jamais `utilisateur` — la seule requête sur cette table (`noms_lisibles`) sert aux verrous de planche, pas au journal. Une chaîne de révision continue donc d'attribuer ses actes à quelqu'un qui n'a plus de compte, ce qui est exactement ce qu'on veut : retirer un droit d'entrée n'efface pas ce qui a été fait
- [x] **Et le verrou de planche ne bloque personne** — vérifié en lisant la route plutôt qu'en le supposant. `verrou_par` est « purement informatif : n'importe qui peut toujours déverrouiller ». Une planche verrouillée par un compte disparu se libère sans recours administrateur. C'est le genre de dépendance qu'on redoute à tort, et la nommer évite de la chercher
- [ ] Le coût réel de la migration `file` → `ldap` sur cette instance : les comptes à recréer, les groupes à reporter, et ce qui se passe pour un TOTP déjà enrôlé. **Hypothèse à éprouver** : les appareils TOTP vivent dans le stockage PROPRE d'Authelia (`db.sqlite3`), indexés par nom d'utilisateur et non par backend — à noms d'utilisateur identiques, ils devraient suivre. Se vérifie sur l'instance : `docker compose exec authelia sh -c "authelia storage user totp export --config /config/configuration.yml"` ou, à défaut, la table `totp_configurations` de `db.sqlite3`

### Ce que BDéditeur pourrait apporter, et qu'aucun annuaire ne saura
- [ ] La demande dit « comptes ACTIFS », et un annuaire ne connaît que les comptes DÉCLARÉS. `utilisateur` porte `premiere_vue` et `derniere_vue` : BDéditeur sait qui a réellement ouvert l'application, et quand. Un tableau en lecture seule dans le panneau 👥 Collections répondrait à la moitié « voir » de la demande, sans dépendre du chemin choisi pour la moitié « créer »
- [ ] Ce tableau croise l'usage et les accès : qui a une portée vide alors qu'il s'est connecté — c'est-à-dire quelqu'un qui attend un droit qu'on a oublié de lui donner. Personne ne voit ce cas aujourd'hui, ni côté Authelia ni côté application

## Contexte

Distinct d'`AUTH-6`, qui porte le MODÈLE — combien de comptes, quels groupes, quels droits.
Celui-ci porte l'OUTILLAGE de ce modèle une fois arrêté. Les deux se lisent ensemble : il
serait absurde de choisir un annuaire avant de savoir quels groupes on veut, et tout aussi
absurde d'arrêter un modèle sans savoir ce qu'il coûtera à administrer.

Le premier morceau d'AUTH-6 a déjà été pris le 2026-09-06 — comptes nominatifs en
`one_factor`, second facteur pour `bd-admins` et sur la sauvegarde (cf. `INFRA-8`). Il
rend ce chantier plus urgent, pas moins : sans second facteur à enrôler, il ne reste qu'un
mot de passe à créer, donc plus rien qui justifie un passage par la console.
