---
chantier: AUTH-1
statut: différé
---

# AUTH-1 — faire entrer l'identité dans l'application

**Arrêté sur** — le commit `f3fc5a7`, 31 août : les deux cases d'interface sont faites, et
le dossier a sa quatrième nature. Le verrou dit enfin PAR QUI (`verrou_par_nom`, miroir
`utilisateur`) — « par vous » se décidant sur le LOGIN et non sur le nom affiché, que deux
personnes peuvent partager. Les groupes servent là où ils DISTINGUENT trois pannes que le
même bandeau vide confondait, et nulle part ailleurs. Le cliquet d'AUTH-5 a refusé au
passage la sorte `nom` nouvellement émise tant qu'elle n'était pas déclarée : il a servi
huit heures après avoir été écrit. Ce qui reste ne dépend plus de moi — d'où le passage en
`différé`, comme DEPOT-1.

Avant lui, le commit `b11661d`, 31 août : l'identité est NOMMÉE en base et PSEUDONYMISÉE à la sortie. De onze surfaces émettrices à six, et plus aucune n'est un artefact de dépôt — l'identité circule dedans, elle ne sort plus dans ce qui est figé, l'axe de DROIT-1 appliqué aux personnes. `GET /api/export/json` nomme aussi ses colonnes : il faisait `SELECT *`, donc `verrou_par` et les chemins serveur partaient au dépôt, et une colonne neuve se publiait par défaut plutôt que par décision.

Avant lui, le commit `e9c44ff`, 31 août : le sort de `GET /api/analyse/accord-inter`
est tranché, en DEUX endroits — la route (réservée à qui écrit) et le dépôt (les taux,
jamais les noms). L'occasion a montré que l'énumération du 31 août, pourtant déjà la
troisième, était elle-même courte d'un chemin : l'onglet XLSX de
`metadonnees_collection.py` publiait les logins, et c'est la suite qui l'a dit en cassant.

Avant lui, 2026-08-27, `247c145` : garde de confiance, groupes, miroir `utilisateur` (v22)
et verrou attribué sont livrés et vérifiés dans l'image. Reste l'exposition dans l'UI.

**Relue le 2026-08-28**, après DROIT-1 et SHARE-1, qui touchent tous deux à la case des
sauvegardes sans la refermer — l'un a réduit l'audience, l'autre a tracé le geste et
rendu explicite un chemin de sortie personnel. La relecture a surtout trouvé qu'une
affirmation du contexte était INCOMPLÈTE : la sauvegarde n'est pas la seule voie de sortie.
Aucun commit de code : le chantier reste `interrompu` là où il l'était.

## Reste

### Lire ce qui arrive déjà
- [x] `Remote-Groups` est lu et exposé par `GET /api/moi` (liste découpée sur les virgules ; `[]` en l'absence d'en-tête, contrat stable pour l'UI)
- [x] `Remote-Name` était déjà lu ; `Remote-Email` l'est désormais et alimente le miroir

### Une identité en base, sans second système d'auth
- [x] Table `utilisateur` (v22), clé = login Authelia, ligne créée à la première visite via `/api/moi` ; aucun secret en base, vérifié par un test qui refuse toute colonne password/hash/token
- [x] Les groupes ne sont PAS stockés : relus à chaque requête, donc un retrait dans `users_database.yml` prend effet immédiatement. Un test refuse toute colonne `groupes`/`role`
- [x] Le mono-poste local reste identique (agent NULL, acte anonyme) — et va plus loin : sans `BD_AUTH_PROXY`, une en-tête FORGÉE est ignorée, vérifié dans l'image

### Ce que l'identité débloque immédiatement
- [x] Le verrou de planche consigne qui l'a posé (`planches.verrou_par`, v22)
- [x] **L'UI affiche qui a verrouillé une planche**, avec le nom lisible plutôt que le login (`verrou_par_nom`, servi par `database.noms_lisibles` sur `GET /api/albums/{id}/planches` et sur le retour du PATCH, pour que l'écran qui vient de poser le verrou n'affiche pas un login jusqu'au rechargement). Le miroir `utilisateur` sert enfin à quelque chose. Deux points valaient d'être tranchés. **« Par vous » se décide sur le LOGIN**, jamais sur le nom d'affichage : deux personnes peuvent le partager, et se voir attribuer le verrou d'un homonyme serait pire que de ne rien dire — le login RESTE donc dans la charge utile, et le cliquet d'AUTH-5 l'y a fait déclarer avec sa raison. **Le repli est le login lui-même** quand le miroir ne sait rien (compte qui n'a jamais ouvert l'app, proxy sans `Remote-Name`) : un identifiant imparfait vaut mieux qu'un trou, et l'appelant n'a jamais à distinguer les deux cas. Rien ne change en mono-poste, où l'agent est NULL — un acte anonyme, honnêtement
- [x] **L'UI affiche les groupes là où ils SERVENT**, et pas « là où c'est utile » : le bandeau de portée vide, parce qu'ils y DISTINGUENT trois pannes que le même écran confondait — aucune identité ne parvient (forward_auth muet) ; une identité mais aucun groupe (le proxy pose `Remote-User` sans `Remote-Groups`) ; une identité AVEC ses groupes, dont aucun n'a d'accès. Les deux premières se réparent, la troisième non : les confondre envoie quelqu'un chercher une panne qui n'existe pas, ou en ignorer une qui existe. La liste EST le diagnostic, et on ne la commente pas. Plus l'infobulle de la pastille, pour la faute de frappe dans un nom de groupe — qui n'ouvre rien SANS LE DIRE (invariant d'AUTH-2), et que personne ne pouvait vérifier. Au passage `/api/moi` n'est plus demandé qu'UNE fois par page (`window.BDMoi`, promesse partagée par `theme.js`) : trois surfaces l'appelaient chacune, et chaque appel réécrit dans le miroir

### Données personnelles — angle mort du projet
> **Ce que le 2026-08-31 a changé, sans refermer les deux cases.** L'angle mort n'en est
> plus un : `docs/dossier-base-legale.md` porte désormais une **quatrième nature de
> donnée** — l'outil détient un fichier de personnes (login, nom, adresse dans
> `utilisateur` ; traces nominatives dans le journal A3 ; `token_correction.auteur` et
> `planches.verrou_par`) — et **quatre questions numérotées 9 à 12** : durée de
> conservation, effacement d'un partant, sort des sauvegardes déjà déposées, responsable
> de traitement et information de l'intéressé. Le dossier ne conclut rien, comme pour les
> œuvres : il porte la question à qui sait y répondre. La question 10 est celle qui coince,
> et il vaut mieux qu'elle soit posée franchement — le journal est append-only, et c'est
> exactement ce qui lui donne sa valeur probatoire au § 1 du dossier. Effacer quelqu'un qui
> le traverse, c'est défaire ce qu'on cherche à démontrer.
>
> Les deux cases ci-dessous restent donc ouvertes, et **c'est leur état normal** : elles
> attendent une réponse institutionnelle, pas du code. Elles ont seulement cessé d'attendre
> que quelqu'un pense à les poser. C'est ce qui fait passer AUTH-1 en `différé`.
- [ ] Le sort des données personnelles d'annotateurs (`utilisateur.nom`, `utilisateur.email`) est tranché et écrit : combien de temps on les garde, ce qu'on en fait, comment on efface quelqu'un qui quitte l'équipe
- [ ] La conséquence sur les sauvegardes est traitée : `VACUUM INTO` (`pipeline/backup.py:28`) emporte la base ENTIÈRE, donc ces emails, et `pipeline/sharedocs.py` sait déposer ce zip sur ShareDocs — donc hors de la machine
> **Ce que le 2026-08-28 a changé, sans refermer la case.** DROIT-1 a réservé les deux
> routes de sauvegarde aux ADMINISTRATEURS : l'audience se réduit, la question reste
> entière — combien de temps garde-t-on ces emails, comment efface-t-on quelqu'un. SHARE-1
> a rendu le dépôt ShareDocs JOURNALISÉ (qui a déposé, sous quel compte), donc la sortie
> est désormais tracée, ce qu'elle n'était pas ; mais il a aussi rendu EXPLICITE le choix
> de déposer sous un compte Huma-Num PERSONNEL. La possibilité existait déjà — la session
> unique pouvait être celle de n'importe qui — mais elle est maintenant offerte dans
> l'écran, donc probable. Ces emails peuvent atterrir dans un espace individuel que
> l'institution ne contrôle pas.
- [x] **La deuxième voie de sortie est traitée**, découverte en relisant le 2026-08-28 : `tools/provenance_export.py` émet les LOGINS des annotateurs — `bd:agent/<login>` en PROV-JSON, `who="#<login>"` et « par <login> » en TEI. Ce n'est pas l'email ni le nom lisible (qui restent dans le miroir `utilisateur`, donc dans la seule sauvegarde), mais un login identifie une personne. Deux circonstances jouent en sens contraire : c'est un outil de LIGNE DE COMMANDE, sans route HTTP, donc il suppose un accès shell — mais il est fait pour être DÉPOSÉ, la sérialisation PROV-O étant tout l'objet de la piste A. Autrement dit, ces logins ont vocation à partir dans un dépôt public **TRAITÉE le 2026-08-31 (`b11661d`)** : l'agent humain est PSEUDONYMISÉ dans les deux sérialisations (`annotateur-N`), les moteurs gardant leur nom — ce sont des logiciels, et les nommer EST l'auditabilité revendiquée. Le mapping (`tools/_commun.pseudonymes`) est PARTAGÉ avec les trois chemins de `metadonnees_collection.py`, sans quoi deux artefacts du même export nommeraient autrement la même personne. Ordonné par PREMIÈRE TRACE et non par l'alphabet : un arrivant renumérote sinon tous ceux qui le suivent, et deux dépôts du même corpus décriraient des équipes différentes
- [x] **Les voies de sortie sont ÉNUMÉRÉES, et non listées de mémoire** — l'inventaire refait le 2026-08-31 en cherchant qui LIT `evenement`, `activite` et `utilisateur` en trouve six, dont trois que les deux relectures précédentes avaient manquées : `tools/metadonnees_collection.py` exporte `agent` comme COLONNE NOMMÉE dans `evenement.csv` et `activite.csv`, avec les blobs `avant`/`apres` ; `tools/description_collection.py` embarque le bloc accord-inter, soit `auteurs` (des logins) et `paires` (deux logins chacune) ; et surtout `GET /api/analyse/accord-inter` (`main.py:3635` → `accord_inter.py:50`) rend la même chose par une ROUTE HTTP. **Et l'énumération elle-même était courte d'un chemin** : `metadonnees_collection.py` a TROIS sorties et non deux — le JSON, les CSV et l'onglet XLSX `qualite`, qui publiait les logins joints par « ; ». C'est la suite qui l'a dit, en cassant, le 2026-08-31 ; aucune des trois relectures ne l'avait vu. Cette dernière change la nature du problème : les cinq autres supposent un accès shell ou le droit d'administrer, celle-ci est atteignable par toute personne simplement admise sur une collection **Fermée le 2026-08-31 par [AUTH-5](AUTH-5.md)**, et pas en énumérant une cinquième fois : `tests/test_sorties_identite.py` sème trois sentinelles — un login, un nom lisible, un courriel — balaie 61 surfaces et EXIGE que chacune où l'une apparaît soit déclarée avec sa raison. L'inventaire cesse d'être une phrase dans une fiche, qui pourrit, pour devenir quelque chose qui casse. Le balayage a d'ailleurs corrigé cette énumération-ci : il trouve 11 surfaces émettrices, dont `/api/export/json` et `/api/regions/{id}/tokens`, qu'aucune des quatre passes n'avait citées
- [x] **Le sort de `GET /api/analyse/accord-inter` est tranché** le 2026-08-31, et en DEUX endroits — la route n'était pas la sortie la plus grave. (a) La ROUTE est réservée à qui ÉCRIT (403 sinon), et son périmètre suit les albums où l'on écrit et non ceux qu'on lit : *ceux qui voient la mesure sont ceux qu'elle mesure*, les propriétaires cumulant l'écriture. Le bouton 👥 Inter reste VISIBLE et le panneau affiche le refus du serveur — il l'écrasait par « Impossible de charger le rapport », transformant une décision motivée en panne apparente. Réserver aux ADMINISTRATEURS a été écarté : `bd-admins` est un rôle d'exploitation, l'accord inter-annotateurs un instrument scientifique ; le donner à qui tient le serveur en le retirant à l'équipe qu'il mesure serait un contresens. (b) Le DÉPÔT ne porte plus de noms : `qualite.accord_inter` était classé `ouvert` et emportait `auteurs` (les logins) et `paires` (le taux d'accord de deux personnes NOMMÉES) vers l'entrepôt, DÉFINITIVEMENT. Il porte `nb_auteurs` et des paires anonymes triées par taux — triées par `(a, b)`, l'ordre alphabétique des logins transparaissait à travers des noms retirés. La valeur FAIR revendiquée est intacte : « relu à plusieurs, accord 0,87 » ne demande aucun nom. L'outil CLI, lui, nomme toujours : sans les noms on ne peut pas réunir deux personnes pour arbitrer

## Contexte

**C'est la fiche la moins chère du lot et elle débloque tout le reste** : sans notion
d'utilisateur en base, ni AUTH-2 (autorisation), ni AUTH-3 (espaces), ni INFRA-3
(identifiants ShareDocs par personne) ne peuvent s'écrire.

La doctrine du dépôt reste intacte : **pas d'authentification dans le code**. Authelia
authentifie, l'application se contente de croire l'en-tête que le proxy pose — ce qu'elle
fait déjà depuis INFRA-2. On n'ajoute pas un système de comptes, on branche celui qui
existe : `deploy/authelia/users_database.yml` porte déjà un compte `chercheur` dans un
groupe `annotateurs`, et Authelia est en `default_policy: deny` avec 2FA.

**Angle mort découvert le 2026-08-27 en relisant ce chantier.** Le dépôt documente
minutieusement les droits du CORPUS — `base_legale`, `statut_diffusion`, tiering,
exception TDM — et ne dit **rien**, nulle part, des données personnelles des personnes
qui l'utilisent : aucune occurrence de « données personnelles », « RGPD » ou
« anonymisation » dans `docs/` ni dans `AUDIT.md`. AUTH-1 est le premier chantier à en
stocker (nom, email), et il le fait sans que rien n'encadre cette catégorie. Le volume est
minime et l'équipe petite ; ce n'est pas un blocage. C'est une lacune de doctrine, à
combler pendant qu'elle est petite plutôt qu'après. Recoupe DEPOT-1, qui porte l'autre
moitié de la question juridique.

Vérifié le 2026-08-27, puis corrigé DEUX fois — et il vaut la peine de garder les trois
états, parce que c'est la même erreur qui se répète.

1. **2026-08-27** — « les exports (records, CSV, IIIF, crosswalk) n'énumèrent pas les
   tables et ne laissent fuir aucun email ; la seule voie de sortie est la sauvegarde ».
2. **2026-08-28** — incomplet : `tools/provenance_export.py` sérialise le JOURNAL et porte
   les logins des agents. Le constat sur les emails et les noms lisibles tient (ils ne
   sortent que par la sauvegarde) ; s'ajoute une catégorie qu'on n'avait pas regardée,
   l'identifiant, qui désigne une personne sans la nommer.
3. **2026-08-31** — incomplet encore, et la deuxième correction avait été faite de mémoire
   comme la première. En énumérant cette fois ce qui LIT `evenement` / `activite` /
   `utilisateur`, on trouve **six** voies : la sauvegarde (entière, réservée aux
   administrateurs depuis DROIT-1), son dépôt ShareDocs (même réserve),
   `provenance_export.py`, `metadonnees_collection.py` (`evenement.csv` et `activite.csv`,
   colonne `agent` NOMMÉE, plus les blobs `avant`/`apres`), `description_collection.py`
   (bloc accord-inter : `auteurs`, `paires`), et `GET /api/analyse/accord-inter`. La
   dernière est une ROUTE HTTP : elle ne suppose ni shell ni droit d'administrer.

La leçon vaut au-delà de cette fiche, et elle a fallu trois fois pour être écrite
proprement : un inventaire de voies de sortie se fait en ÉNUMÉRANT ce qui lit les tables
d'identité, pas ce dont on se souvient. Les deux premières passes ont fouillé les exports
qu'on avait en tête — et à chaque fois, ce qui manquait avait été ajouté pour d'excellentes
raisons (A3 pour la provenance, ANN-5 pour l'accord inter-annotateurs) par un chantier qui
ne se pensait pas comme une voie de sortie.

Conséquence de sûreté, traitée : ces en-têtes ne sont dignes de confiance **que** derrière
le proxy. C'était vrai depuis INFRA-2 sans être garanti — la docstring affirmait « l'app
n'est jamais exposée en direct », ce qui est une hypothèse sur le déploiement, pas une
propriété du code. `BD_AUTH_PROXY` en fait une propriété du code (`247c145`), et le
compose pose le drapeau. Inoffensif tant que rien n'est autorisé sur cette base ; c'eût
été une escalade de privilège en une ligne de `curl` dès AUTH-2.
