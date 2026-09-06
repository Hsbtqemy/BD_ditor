---
chantier: AUTH-7
statut: interrompu
---

# AUTH-7 — administrer les comptes sans console

**Arrêté sur** — 2026-09-06, `e193ae4` : **la vérification la moins chère est faite, elle
n'annule rien — elle ferme l'attente. Et la suivante a retourné le problème.** La demande
voulait les deux gestes actifs, supprimer et désactiver, la désactivation étant vue comme
un pis-aller. C'est l'inverse : dans cette architecture, désactiver est complet et
réversible depuis un panneau, tandis que **supprimer laisse quatre orphelins** dont un ne
se nettoie qu'en console — et dont le quatrième ment dans la vue qui devait rassurer. La
suppression n'est donc offrable qu'à une condition, et cette condition a changé de nature
le jour même. Ce n'est pas la FORME du login, écartée par
l'équipe comme une friction à chaque arrivée : c'est ce que le compte a **laissé**. Rien au
journal ni dans `collection_acces` : on supprime. Quelque chose : on archive. La règle est
validée et son critère mesuré — deux requêtes, et **naviguer ou lire ne laisse rien**.
L'équipe a choisi de garder la suppression comme geste courant du panneau, la vue servant
de garde-fou : la vigilance redevient donc la garantie, en connaissance de cause, et toute
la charge passe sur la vue des comptes — qui doit rendre un VERDICT et signaler le retour
d'un login connu.

Le même jour, plus tôt : **aucune version d'Authelia n'administre les comptes**, et la
plus récente non plus — sur sa feuille de route, « User Management » n'est pas commencé et
ne porte aucune version cible. Attendre n'est donc pas une option ; il reste à choisir
entre l'annuaire et le fichier. Un constat collatéral est parti dans `INFRA-9` : cette
instance tourne sur une mineure qui ne reçoit plus de correctifs de bogue.

**La demande, en propres termes** — 2026-09-06 : *« pouvoir gérer la création
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

Conséquence sur la section « ce que BDéditeur pourrait apporter » plus bas, **révisée le
2026-09-06** : la vue de l'usage (`premiere_vue`/`derniere_vue`) n'est toujours pas la
demande, et elle ne conditionne toujours aucun choix d'annuaire — le cadrage de l'équipe le
confirme même : *l'annuaire sert à FAIRE, pas à SAVOIR*. Mais elle a cessé d'être un
bonus. Depuis que la suppression reste un geste courant du panneau, **c'est elle qui la
rend sûre**, et les deux exigences qui l'accompagnent ne sont plus facultatives.

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

**Corrigé le 2026-09-06 — LLDAP ne sait pas désactiver**, et ce chemin s'écrivait comme si
c'était acquis. L'issue lldap#750 le demande depuis le 2 décembre 2023, *help wanted*,
toujours ouverte, sans PR. Le chemin tient quand même, mais pour une raison qu'il faut
écrire : **la désactivation n'a pas à venir de l'annuaire.** Elle vient d'`access_control`,
par une règle `deny` en tête sur un groupe `archives` — et ce qu'on demande alors à LLDAP,
c'est de gérer une APPARTENANCE de groupe, ce qu'il fait nativement et bien. Ne pas confier
à l'annuaire ce que le proxy tranche déjà est d'ailleurs cohérent avec AUTH-1 : l'annuaire
dit QUI, Authelia dit s'il entre.

**3. Un outil d'administration écrit ici.** À écarter, sauf raison forte : il faudrait
manipuler des hashs de mots de passe, orchestrer un redémarrage d'Authelia, et surtout ce
serait un outil DISTINCT de BDéditeur — l'application n'authentifie personne (AUTH-1), et
lui confier la base d'authentification effondrerait le raisonnement de sécurité entier.
Écrire un gestionnaire de comptes est un métier ; LLDAP le fait déjà.

## Reste

### Trancher (la décision appartient à l'équipe)
- [x] Le rythme d'arrivée est cadré — **2026-09-06, par l'équipe** : le projet est aujourd'hui porté par un projet unique, mais il va s'ouvrir à d'autres personnes, avec des activités liées à certains COURS, donc des corpus très spécifiques et des groupes qui changent. Ce n'est plus « deux comptes stables ». Le motif redouté est nommé : *« on pourrait trop rapidement devoir gérer un SAV à l'aveugle »* — administrer sans voir. Cela déplace la balance vers le chemin 2, sans le trancher : c'est la case suivante
- [ ] **L'annuaire retenu sait DÉSACTIVER un compte sans le supprimer** — mesuré pour les trois candidats le 2026-09-06. **LLDAP : non**, issue #750 ouverte depuis le 2 décembre 2023, *help wanted*, sans PR. **Kanidm : oui, mais son admin passe par la CLI** — sa web UI vise le libre-service et ses panneaux d'admin ont été retirés, donc hors critère. **Authentik : oui**, et il REMPLACE Authelia. La case reste ouverte parce que la conception a bougé : la désactivation vient désormais d'une règle `deny`, pas de l'annuaire — ce qui rend la réponse de LLDAP non disqualifiante
- [x] **Le login ne portera PAS l'année** — tranché le 2026-09-06 par l'équipe : *« pas les années, ça me paraît beaucoup trop éloigné des préoccupations de facilitation. Tant qu'on peut créer des comptes, on n'a pas à être gêné par ça. »* Un login qu'on n'ose pas dicter coûte à chaque arrivée, pour un risque rare : faire payer le cas courant pour le cas rare est le mauvais échange. La non-réutilisation ne peut donc plus reposer sur la forme du login, et se déplace — case suivante
- [ ] **`premiere_vue` ne survit pas à un login réutilisé** — l'UPSERT de `main.py` ne la met pas dans son `DO UPDATE`, donc la vue des comptes daterait un arrivant de l'arrivée de son prédécesseur. Attendu : soit la suppression d'un compte efface sa ligne `utilisateur`, soit la vue signale la reprise d'un login connu. C'est le seul des quatre orphelins qui vive dans une table de BDéditeur, donc le seul réparable sans console — et il ment dans l'instrument même dont la règle ci-dessous dépend
- [x] **La règle est validée, et son critère est MESURÉ** — 2026-09-06. Ce qui décide, c'est ce que le compte a LAISSÉ, et « laisser » se réduit à deux requêtes : `SELECT COUNT(*) FROM evenement WHERE agent = ? AND agent_type = 'humain'` et `SELECT COUNT(*) FROM collection_acces WHERE genre = 'utilisateur' AND principal = ?`. Zéro aux deux → la suppression n'orpheline rien. Autre chose → on archive. **Aucune session humaine n'ouvre d'activité** — `ouvrir_activite` n'est appelé que par `passe_ml` et le réindex NLP, deux agents machine —, donc naviguer, chercher et lire ne laissent RIEN : seules les 18 routes d'écriture journalisent. La règle est ainsi plus étroite qu'annoncée, et c'est ce qui la rend praticable
- [x] **La suppression reste un geste courant du panneau, à côté de créer et archiver** — tranché le 2026-09-06 par l'équipe, la vue servant de garde-fou consulté avant. **La contrepartie est acceptée en connaissance de cause** : la vigilance redevient la garantie, alors que la fiche cherchait à s'en passer. Elle se paie donc sur la VUE, qui n'est plus un tableau à interpréter mais l'unique chose qui empêche une suppression fautive — voir les deux cases de la zone suivante, qui étaient des conforts et deviennent des exigences
- [ ] **Le rythme d'arrivée RÉEL est chiffré** — c'est le fait qui départage LLDAP et Authentik, et personne hors de l'équipe ne l'a. Trente personnes par cours et deux cours par an, ou une poignée par an ? Sous le second régime LLDAP gagne largement ; sous le premier, le lien d'invitation d'Authentik paie le remplacement à lui seul. Tant que ce chiffre manque, le choix se fait au jugé
- [ ] Le chemin est choisi entre les trois ci-dessus, et la raison est écrite — y compris si c'est « on garde le fichier », qui est un choix légitime tant que le rythme reste faible

### Ce qu'il faut savoir AVANT de choisir (mesures, pas opinions)
- [x] **Une version plus récente d'Authelia administre-t-elle les comptes ? NON — et pas davantage la prochaine.** Vérifié le 2026-09-06 sur la feuille de route officielle (relevé du 2026-08-24, donc à jour) et sur les publications : la dernière version est 4.39.22, du 2026-09-03, et rien n'y administre de comptes. L'entrée « Dashboard / Control Panel and CLI for Administrators » est ACTIVE, mais l'étape *Design* est seule « in progress » ; l'*Initial Implementation* vise 4.40.0 sans être commencée, et **« User Management » n'est pas commencé et ne porte aucune version cible du tout** — c'est la DERNIÈRE étape de la liste. La vérification était censée pouvoir annuler la moitié de la fiche ; elle fait l'inverse et **ferme l'attente**, ce qui a la même valeur : on ne diffère plus le choix en espérant qu'amont le règle
- [x] Ce que devient une collection dont on supprime le dernier propriétaire **hors de l'application** — reproduit le 2026-09-06 (`test_un_proprietaire_disparu_laisse_une_collection_administrable_par_un_admin_seul`). **Ce n'est pas une impasse, mais elle exige un administrateur.** La ligne survit : la collection garde un propriétaire FANTÔME, qui ne peut plus se connecter. Un tiers ne voit rien (404). L'administrateur ne peut pas retirer le fantôme tel quel — le 409 « dernier propriétaire » l'en empêche, et il a raison. La seule sortie : désigner un remplaçant, PUIS retirer. Faisable entièrement à l'écran, sans SQL — mais impossible sans `bd-admins`
- [x] Ce que devient le journal A3 quand l'agent cité n'existe plus : **il survit**, et par construction. `activite.agent` est une colonne TEXTE sans clé étrangère, et rien ne joint jamais `utilisateur` — la seule requête sur cette table (`noms_lisibles`) sert aux verrous de planche, pas au journal. Une chaîne de révision continue donc d'attribuer ses actes à quelqu'un qui n'a plus de compte, ce qui est exactement ce qu'on veut : retirer un droit d'entrée n'efface pas ce qui a été fait
- [x] **Et le verrou de planche ne bloque personne** — vérifié en lisant la route plutôt qu'en le supposant. `verrou_par` est « purement informatif : n'importe qui peut toujours déverrouiller ». Une planche verrouillée par un compte disparu se libère sans recours administrateur. C'est le genre de dépendance qu'on redoute à tort, et la nommer évite de la chercher
- [ ] **Les panneaux TIERS sont évalués avant d'en écrire un.** `asalimonov/authelia-admin` se présente comme un panneau de gestion des utilisateurs, groupes, appareils TOTP et bannissements — exactement la moitié « créer / activer / désactiver » du critère. **Trois réserves, et aucune n'est levée au 2026-09-06** : il s'annonce pour une intégration LLDAP, donc il PRÉSUPPOSE le chemin 2 au lieu de l'éviter ; sa page visible ne mentionne que créer / éditer / supprimer, jamais désactiver, ce qui manquerait le modèle « pas de suppression, désactivation et archivage » ; et il demande l'accès au fichier de configuration ET à `db.sqlite3` d'Authelia, c'est-à-dire un couplage à un schéma privé que chaque montée de version peut rompre (`INFRA-9`). Projet à 200 étoiles, 6 forks, MIT — un candidat, pas un composant d'Authelia
- [ ] **Une règle `deny` en tête d'`access_control` refuse bien l'accès à l'application** — à ÉPROUVER sur l'instance, pas déduit de l'ordre promis. Attendu : un compte du groupe `archives` est refusé sur `bd.edito-revue.fr` alors que les trois règles suivantes l'autoriseraient, et l'effet porte sur une session DÉJÀ ouverte, la portée se recalculant à chaque requête. Le portail `auth.` reste joignable, ce qui est sans importance — il n'y a rien derrière
- [ ] **Ce que devient un TOTP orphelin quand le login revient** — la seule des quatre conséquences de la suppression qui ne se lise pas dans le code d'ici, donc la seule à mesurer sur l'instance. Attendu à confirmer : le stockage d'Authelia étant indexé par nom d'utilisateur et indépendant du backend, le nouvel arrivant ne peut PAS s'enrôler — une configuration existe déjà — pendant que l'appareil de l'ancien produit encore des codes valides pour ce login. Se mesure en supprimant un compte d'essai puis en le recréant sous le même nom — **la même manipulation répond à la case de migration ci-dessous**, qui interroge la même propriété dans l'autre sens : ce qui fait SUIVRE un TOTP au changement de backend est ce qui le fait RESTER après une suppression
- [ ] **Si Authentik : le séparateur de groupes est traité DANS LE MÊME GESTE que le renommage d'en-têtes** — mesuré le 2026-09-06, et c'est une soirée épargnée. `autorisation.py:96` découpe `Remote-Groups` sur des VIRGULES ; Authentik sépare `X-authentik-groups` par des PIPES. Attendu : soit un mapping de propriété qui émet des virgules et BDéditeur ne bouge pas d'une ligne, soit une ligne qui découpe sur les deux. Jamais après la bascule — la panne se ferme en silence et le bandeau d'AUTH-1 accuse le mauvais coupable (voir plus bas)
- [ ] Le coût réel de la migration `file` → `ldap` sur cette instance : les comptes à recréer, les groupes à reporter, et ce qui se passe pour un TOTP déjà enrôlé. **Hypothèse à éprouver** : les appareils TOTP vivent dans le stockage PROPRE d'Authelia (`db.sqlite3`), indexés par nom d'utilisateur et non par backend — à noms d'utilisateur identiques, ils devraient suivre. Se vérifie sur l'instance : `docker compose exec authelia sh -c "authelia storage user totp export --config /config/configuration.yml"` ou, à défaut, la table `totp_configurations` de `db.sqlite3`

### Ce que BDéditeur pourrait apporter, et qu'aucun annuaire ne saura
- [ ] La demande dit « comptes ACTIFS », et un annuaire ne connaît que les comptes DÉCLARÉS. `utilisateur` porte `premiere_vue` et `derniere_vue` : BDéditeur sait qui a réellement ouvert l'application, et quand. Un tableau en lecture seule dans le panneau 👥 Collections répondrait à la moitié « voir » de la demande, sans dépendre du chemin choisi pour la moitié « créer ». **Promu le 2026-09-06 de confort à CONDITION** : depuis que la sûreté d'une suppression se juge sur ce que le compte a laissé, c'est ce tableau qui doit le dire — il lui faut donc, en plus de l'usage, le compte d'actes au journal A3 et les accès détenus
- [ ] Ce tableau croise l'usage et les accès : qui a une portée vide alors qu'il s'est connecté — c'est-à-dire quelqu'un qui attend un droit qu'on a oublié de lui donner. Personne ne voit ce cas aujourd'hui, ni côté Authelia ni côté application
- [ ] **La vue rend un VERDICT, pas des chiffres** — « aucun acte, aucun accès : supprimable » ou « 42 actes, 2 collections : à archiver », et les comptes sont GROUPÉS par verdict. Exigence née du choix du 2026-09-06 : un tableau de nombres demande d'interpréter au moment où l'on est pressé, ce qui est précisément la vigilance qu'on voulait éviter. Lire dans quelle liste quelqu'un se trouve demande moins que compter ses actes
- [ ] **La vue signale le RETOUR d'un login connu** — le filet quand la vigilance a manqué. Le geste de suppression vit dans l'autre panneau et rien ne peut l'empêcher ; ce qui reste possible, c'est de voir qu'un login réapparaît alors que `utilisateur` en garde déjà la ligne, avec des actes au journal. C'est la différence entre une provenance corrompue en silence et une provenance corrompue signalée — et c'est bon marché, la ligne étant déjà là

## La vérification qui devait annuler la fiche — 2026-09-06

Elle a rendu une réponse claire et un effet qu'on n'attendait pas : **elle ne retire rien
du travail, elle retire une raison d'attendre.** C'est le meilleur usage d'une mesure à
dix minutes — non pas trouver une économie, mais empêcher qu'on remette la décision à une
version qui n'arrive pas.

Le détail compte, parce qu'une lecture rapide de la feuille de route dirait le contraire.
L'entrée existe, elle est classée ACTIVE, et elle annonce 4.40.0 : de quoi conclure « c'est
pour bientôt, attendons ». Mais 4.40.0 ne concerne que l'*Initial Implementation*, la
*Segregation*, la gestion des SESSIONS et celle des clients OpenID Connect. **La gestion
des UTILISATEURS est la dernière étape de la liste, elle n'est pas commencée, et elle est
la seule à ne porter aucune version.** Ce n'est donc pas « la prochaine version » : c'est
une étape sans date, derrière quatre autres.

## Changer de gestionnaire ne réglerait presque rien — sauf l'inscription — 2026-09-06

Question posée en séance : les orphelins seraient-ils différents ailleurs ? La réponse
protège surtout une décision future.

**Trois des quatre sont à NOUS**, et aucun annuaire ne les touche : `collection_acces`,
`evenement` et `utilisateur` sont des tables de BDéditeur, clées sur un login.

| Orphelin | Où il vit | Fichier | LLDAP | Kanidm (backend) | Authentik (remplace) |
|---|---|---|---|---|---|
| Droits `collection_acces` | BDéditeur | oui | oui | oui | oui\* |
| Provenance `evenement` | BDéditeur | oui | oui | oui | oui\* |
| Second facteur | Authelia `db.sqlite3` | oui | oui | oui | **non** |
| Miroir `utilisateur` | BDéditeur | oui | oui | oui | oui\* |

Un seul disparaît, et il faut quitter Authelia pour ça : avec un IdP intégré, le compte et
ses facteurs sont le MÊME objet. LLDAP ou Kanidm en backend LDAP n'y changent rien —
Authelia garde ses TOTP dans son stockage, indexés par nom d'utilisateur.

**L'astérisque est le vrai point.** Le problème n'est pas l'annuaire, c'est que **le login
EST l'identité**. Un identifiant stable jamais réattribué rendrait les trois inertes par
construction : c'est la version GRATUITE de la convention de nommage écartée le matin même,
puisque le login resterait `p.durand`, dictable, sans être la clé. Authentik en transmet un
(`X-authentik-uid`). Mais il coûte : le journal A3 est LISIBLE parce que sa clé est un
login, et `rapport_accord_inter.py` nomme exprès — *sans les noms on ne peut pas réunir
deux personnes pour arbitrer*. Cléer sur un identifiant opaque ferait de `utilisateur` une
pièce PORTANTE là où elle n'est qu'un miroir jetable : perdue aujourd'hui elle ne coûte
rien, demain elle emporterait la lisibilité du journal entier.

**Et un système d'authentification écrit ici ? Écarté — pas parce que « c'est
difficile ».** Il faudrait mots de passe, sessions, réinitialisation (avec la MÊME
dépendance SMTP qu'INFRA-8, qui n'est donc pas économisée), second facteur, régulation, et
une revue de sécurité pour toujours. En face, des gains réels qu'il faut reconnaître : un
seul panneau, de vraies clés étrangères entre comptes et droits, plus aucun en-tête à
croire, un service de moins et INFRA-9 qui disparaît. Deux arguments tranchent quand même.

AUTH-1 n'est pas un confort : « aucun secret en base » est ce qui rend l'histoire de
sécurité courte, et `GET /api/sauvegarde` déverserait désormais un fichier de mots de
passe — qui part sur ShareDocs. Surtout, **la surface d'attaque change de CATÉGORIE** :
aujourd'hui rien de BDéditeur n'est joignable sans passer Authelia, donc un défaut n'est
atteignable que par quelqu'un qui a déjà un compte ; un formulaire de connexion est, par
construction, joignable par l'internet entier. Ce n'est pas un degré, c'est un régime, et
c'est vrai même si le code est parfait.

La formule : **on écrirait un système d'authentification complet pour obtenir un écran
d'administration, qui en représente peut-être le sixième.**

**Ce qui retournerait la réponse n'est pas l'administration, c'est l'INSCRIPTION.** Le
geste coûteux n'est pas de gérer trente comptes, c'est de les CRÉER trente fois par
semestre. Authentik envoie un lien d'invitation dont l'inscrit sort avec son mot de passe
choisi ET dans le bon groupe — soit par un flux d'enrôlement par groupe (option native de
l'étape `user_write`), soit par un `groups_to_add` dans les attributs de l'invitation,
qu'une *expression policy* convertit juste avant l'écriture (« Evaluate on plan »
désactivé, « Re-evaluate policies » activé). **La seconde forme est préférable pour une
raison de sécurité** : l'avis `GHSA-9qwp-jf7p-vr7h` décrit un contournement de contrôle
d'accès par réutilisation de jeton, dont les configurations touchées sont exactement
« plusieurs flux d'enrôlement, avec étape d'invitation, accordant des permissions
différentes ». Corrigé depuis 2022 ; mais c'est la forme qui a produit la faille, quand
l'autre fait porter la permission par le jeton lui-même.

Alors la chaîne se boucle — **et c'est AUTH-1 qui le permet.** L'enseignant donne au groupe
`cours-bd-2026` un niveau sur la collection (une fois), crée une invitation portant ce
groupe (une fois), envoie le lien à trente personnes : chacune arrive avec son accès déjà
ouvert, zéro geste d'administration par personne. `collection_acces` référence un NOM de
groupe et ne stocke jamais d'appartenance, les groupes étant relus à chaque requête — ce
qui ressemblait à une limitation, « l'application ne sait rien des gens », est exactement
ce qui laisse un compte naître ailleurs et avoir ses droits immédiatement.

**Un piège mesuré, qui aurait coûté une soirée.** J'ai d'abord affirmé que BDéditeur ne
changerait pas d'une ligne, Caddy sachant RENOMMER un en-tête au passage — c'est vrai et
documenté (`Before>After`, exemple Tailscale). Mais **renommer un champ ne convertit pas sa
valeur** : `autorisation.py:96` découpe sur des virgules, Authentik sépare par des pipes.
L'application recevrait un unique groupe nommé `a|b|c`, qui ne correspond à rien, et
**tous les accès par groupe s'évaporeraient — en silence, en se fermant.** Le bandeau
d'AUTH-1 aggraverait : recevant un groupe NON vide, il conclurait au troisième cas et
afficherait « il n'y a donc rien de cassé » sur une panne de proxy parfaitement réparable.
Il montre la preuve — le pipe est visible — et en tire l'inverse. Encore un instrument qui
approuve en regardant à côté.

## Supprimer et désactiver ne sont pas symétriques — 2026-09-06

La demande voulait **les deux gestes actifs**, la désactivation étant présentée comme un
pis-aller par rapport à la suppression. Les deux restent le bon objectif ; le rapport entre
eux est l'inverse de celui qu'on croyait.

**Supprimer un compte libère son login. Or dans cette application, un login est une CLÉ —
dans quatre tables, et aucune ne porte de contrainte d'intégrité.**

**1. Les droits.** `collection_acces.principal` est du TEXTE sans clé étrangère, et il
entre dans la clé primaire (`database.py`). Rien ne peut nettoyer ces lignes :
l'application n'apprend jamais qu'un compte a disparu, elle ne voit que des en-têtes.
**Recréer le même login rend immédiatement au nouvel arrivant les accès de l'ancien**, sans
qu'aucun écran ne le signale.

**2. La provenance, et c'est la plus grave pour cet outil.** La trace d'un humain vit dans
`evenement.agent` — colonne TEXTE, `agent_type` valant `humain` — et non dans
`activite.agent`, qui porte les passes ML ; la fiche citait d'abord la seconde, corrigé le
2026-09-06. Ni l'une ni l'autre n'a de clé étrangère : c'est voulu, et c'est ce qui fait
survivre le journal à la suppression de sa cible. La même propriété fait qu'un login
réutilisé **fusionne deux personnes RÉTROACTIVEMENT** : ANN-5 mesurerait l'accord
d'une personne avec elle-même, et
`pseudonymes()` les exporterait sous un seul `annotateur-N`. Une donnée de recherche
devient fausse sans que personne ne mente et sans qu'aucun test ne bronche.

**3. Le second facteur.** Supprimer dans l'annuaire ne touche pas le stockage propre
d'Authelia : TOTP et WebAuthn y restent, indexés par nom d'utilisateur. **C'est exactement
la propriété qui rendait la migration `file` vers `ldap` indolore** — l'hypothèse écrite
plus haut dans cette fiche — et elle se retourne ici. Reste à mesurer, c'est une case.

**4. Le miroir d'affichage, trouvé en dernier et le plus gênant** — parce qu'il ment
précisément dans l'instrument censé rassurer. `utilisateur.login` est une CLÉ PRIMAIRE
(`database.py`), donc la ligne survit à la disparition du compte. L'UPSERT de `main.py`
corrige bien `nom` et `email` à la requête suivante… mais **`premiere_vue` n'est pas dans
son `DO UPDATE`** : seuls `nom`, `email` et `derniere_vue` y figurent. Un login réutilisé
hérite donc de la **date d'arrivée de son prédécesseur**, et la vue des comptes montre une
personne « présente depuis mars » qui vient d'arriver. Mesuré, pas déduit.

**Aucun des quatre ne se règle depuis un panneau aujourd'hui.** Le premier se nettoie dans
👥 Collections, mais seulement si l'on y pense — rien ne le rappelle, et ce serait une
seconde chose à retenir au moment précis où l'on cherchait à ne plus rien retenir. Le
deuxième ne doit **pas** être nettoyé : le journal est append-only par construction, et
c'est correct. Le troisième exige `authelia storage user totp delete` et `webauthn delete`,
**console uniquement** — précisément ce que le critère d'acceptation refuse.

**Le quatrième, lui, est le seul qui NOUS appartienne**, et c'est ce qui le rend réparable :
les trois autres vivent chez Authelia ou dans un journal auquel on ne doit pas toucher,
quand `utilisateur` est une table de BDéditeur que la vue des comptes peut nettoyer ou
signaler. C'est aussi ce qui rend l'omission coûteuse — non traitée, elle ferait mentir la
vue à l'endroit exact où on lui demande de garantir quelque chose.

| | complet | depuis un panneau | réversible |
|---|---|---|---|
| **Désactiver** (`archives` + `deny`) | oui, rien ne reste | oui | oui |
| **Supprimer** (annuaire) | non, quatre orphelins | non, un geste en console | non |

**D'où une condition — dont la première version était mauvaise.** Elle tenait au NOM :
un login qui porte l'année ne se réutilise pas. Écartée par l'équipe le jour même, et pour
une raison juste — *« beaucoup trop éloigné des préoccupations de facilitation »*. Un login
qu'on n'ose pas dicter au téléphone coûte à chaque arrivée, quand le risque, lui, est rare.
Faire payer le cas courant pour le cas rare est le mauvais échange, et la règle avait
l'inconvénient des règles de vigilance : elle ne se vérifie pas.

**Ce qui décide n'est donc pas le login, c'est ce que le compte a LAISSÉ.** Aucun acte au
journal A3, aucune ligne dans `collection_acces` : la suppression n'orpheline rien — et
c'est le cas de tous les comptes qu'on supprime vraiment, essais, doublons, personnes
jamais venues. Quelque chose de laissé : on archive. Cette version se **vérifie** au lieu
de se respecter, ce qui est exactement ce qui manquait à la première.

**Et c'est la demande initiale qui la rend applicable.** « Une vue sur tous les comptes
actifs » cesse d'être un confort : elle connaît `premiere_vue`, `derniere_vue`, les accès
détenus, et le journal dit si le login a jamais produit un acte. Le panneau peut donc
écrire « aucun acte, aucun accès — la suppression n'orpheline rien » au lieu de laisser
juger de mémoire. La vue devient ce qui rend la suppression sûre : elle passe de confort à
condition, et c'est le seul morceau de cette fiche qui ne dépende d'aucun chemin.

**Un des quatre orphelins s'éteint d'ailleurs tout seul**, par l'arbitrage du facteur
d'INFRA-8. Le TOTP ne concerne que les comptes qui en ont un, et le second facteur est
CIBLÉ — administrateurs et sauvegarde, pas l'usage courant. Un compte étudiant n'en a donc
pas, et sa suppression n'en laisse pas : l'orphelin ne menace que `bd-admins`,
c'est-à-dire précisément les comptes qu'on ne supprime pas. Réserve à ne pas gommer — le
portail laisse probablement quiconque s'enrôler depuis ses réglages, donc c'est
« normalement pas » et non « jamais ». La case de mesure le dira.

## Le constat collatéral est parti dans `INFRA-9` — 2026-09-06

En cherchant la version qui administrerait les comptes, on a appris **où en est celle qui
tourne** : 4.38.19 quand la dernière publiée est 4.39.22, et la politique de versionnement
d'Authelia ne donne les correctifs de bogue qu'à la dernière mineure. Monter est un geste
d'exploitation, avec sa lecture des notes de version et son retour arrière — ce n'est pas
le travail d'AUTH-7. Le laisser dans cette fiche l'aurait endormi avec elle, qui est
`interrompu` : il a donc sa fiche, `INFRA-9`, avec le détail.

**Ce qui, en revanche, est bien l'affaire d'AUTH-7, c'est l'ORDRE.** Le chemin 2 — ajouter
un annuaire — se poserait sur la version qui tourne aujourd'hui. Choisir un annuaire pour
une mineure qu'on s'apprête à quitter serait le pire enchaînement possible : on éprouverait
l'intégration deux fois, la seconde en ayant oublié pourquoi la première avait conclu ce
qu'elle a conclu. `INFRA-9` passe donc avant la décision ci-dessous, ou avec elle.

## Contexte

Distinct d'`AUTH-6`, qui porte le MODÈLE — combien de comptes, quels groupes, quels droits.
Celui-ci porte l'OUTILLAGE de ce modèle une fois arrêté. Les deux se lisent ensemble : il
serait absurde de choisir un annuaire avant de savoir quels groupes on veut, et tout aussi
absurde d'arrêter un modèle sans savoir ce qu'il coûtera à administrer.

Le premier morceau d'AUTH-6 a déjà été pris le 2026-09-06 — comptes nominatifs en
`one_factor`, second facteur pour `bd-admins` et sur la sauvegarde (cf. `INFRA-8`). Il
rend ce chantier plus urgent, pas moins : sans second facteur à enrôler, il ne reste qu'un
mot de passe à créer, donc plus rien qui justifie un passage par la console.
