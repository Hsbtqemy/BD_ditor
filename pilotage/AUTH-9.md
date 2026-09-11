---
chantier: AUTH-9
statut: à venir
---

# AUTH-9 — une page à soi : ce que l'application sait de vous, et ce que vous en déclarez

**Point de départ** — 2026-09-07, demandé en propres termes : *« ça coûterait quelque chose
d'avoir une interface membre ? derrière le login ? pour les personnes qui ne sont pas une
entité abstraite ou un compte partagé ? (voire pour les comptes partagés, pour donner aussi
des noms historiques aux différentes personnes ayant travaillé sous cette identité
collective ?) »* Rien n'est commencé. Le chiffrage est fait, et il se répartit autrement
qu'on ne l'attendait : la moitié « profil » est presque gratuite, la moitié « identité
collective » est bon marché à CONSTRUIRE et chère à CROIRE.

## Reste

### Trancher (la décision appartient à l'équipe)
- [x] **La surface est la pastille d'identité, PAS `/administration`** — tranché le 2026-09-07 par l'équipe : *« admin est pour les personnes ayant des droits, alors qu'un annotateur (qui a son propre compte mais pas de droits d'admin) peut être nominatif et avoir ses propres info »*. La première proposition visait `/administration` (UX-10), et c'était l'erreur inverse de celle qu'UX-10 corrige : cet écran rassemble ce qui porte sur l'INSTANCE, or ce panneau s'adresse précisément à qui n'administre rien. La pastille `.user-chip` de `static/theme.js` est injectée sur les CINQ surfaces et porte déjà le nom, le login et les groupes — c'est le seul point de l'application qui parle de la personne et de personne d'autre
- [ ] **Modale ou page `/moi` ?** — attendu : tranché avec sa raison, sachant que les deux ne coûtent pas pareil. Une modale `dialog.js` injectée par `theme.js` suit la pastille sur les cinq surfaces et n'ajoute aucune route HTML ; une page est une SIXIÈME surface, donc une entrée dans la liste écrite à la main de `test_csp` (ARCH-2 : son mode d'échec est d'oublier ce qu'on ajoute, et elle a désormais son propre contrôle), une entrée de navigation, et un audit axe de plus
- [ ] **Le panneau existe-t-il en mono-poste ?** — attendu : écrit. Sans proxy, `/api/moi` rend `utilisateur: null` et `theme.js` n'injecte aucune pastille (dégradation propre, INFRA-1) : le panneau disparaîtrait avec elle. C'est probablement juste — seul devant sa machine, on n'a ni portée à consulter ni référent à qui écrire — mais le décider vaut mieux que l'hériter du code qui l'accroche

### Ce qui s'y lit — et il n'y écrit RIEN
- [ ] **Ma portée en clair** — attendu : le panneau dit combien de collections je lis, combien j'écris, lesquelles je possède. `/api/moi` rend aujourd'hui des COMPTEURS (`acces.collections`, `acces.ecriture`) et non des noms ; les nommer est une décision et non un détail — elle ne fuit rien, puisqu'il s'agit de collections que je lis déjà (AUTH-2)
- [ ] **Mes groupes, hors infobulle** — attendu : lisibles dans le panneau. Ils vivent aujourd'hui dans le `title` de la pastille (`theme.js`), c'est-à-dire invisibles au tactile et peu fiables au clavier, alors qu'ils GOUVERNENT ce qu'on voit. Une fois le panneau écrit, l'infobulle peut maigrir plutôt que de porter seule un diagnostic
- [ ] **Ce que j'ai laissé** — attendu : mes actes au journal A3 et mes accès explicites, c'est-à-dire le calcul de `_comptes()` (`routes/collections.py`) restreint à `portee.utilisateur`. **SANS le verdict** : « rien à orpheliner » sert à décider d'une suppression, geste qui n'est pas le mien et qui appartient à AUTH-7. Le montrer ici ferait lire une recommandation là où il n'y a qu'un état
- [ ] **À qui demander** — attendu : le référent d'instance (`BD_REFERENT_NOM` / `BD_REFERENT_CONTACT`, AUTH-4) et le référent des collections que je lis, sans redire le bandeau `.portee-vide`, qui s'adresse à qui ne voit RIEN et n'aurait donc pas de panneau à ouvrir

### Ce que la doctrine dit déjà, et qui n'est donc PAS à rouvrir
- [ ] **La règle qui réserve `/api/comptes` et `accord-inter` n'est pas franchie, elle est instanciée** — attendu : la déclaration AUTH-5 du panneau le dit ainsi, plutôt que d'inventer une exception. La règle est *« ceux qui voient la mesure sont ceux qu'elle mesure »* ; une page qui me montre MES actes en est le cas limite, l'ensemble mesuré et l'ensemble qui regarde étant le même singleton. C'est la raison qui autorise déjà `/api/moi` à parler de son appelant

### Les pièges, mesurés le 2026-09-07
- [ ] **Le panneau n'écrit RIEN dans `utilisateur`** — attendu : écrit, et couvert par un test. `nom` et `email` sont un MIROIR : l'UPSERT de `_enregistrer_utilisateur` (`main.py`) les réécrit depuis `Remote-Name` / `Remote-Email` à chaque rafraîchissement passé le TTL. Une écriture applicative marcherait à l'écran, se ferait écraser sans bruit — et surtout déclencherait `_identite_reprise`, donc un événement A3 et la colonne **Signal** en rouge dans la vue des comptes. Polluer l'instrument qu'AUTH-7 a construit pour repérer un login qui change de mains est pire que ne pas offrir le geste
- [ ] **« Changer mon mot de passe » n'entre pas dans l'application** — attendu : le panneau RENVOIE à l'annuaire, ou bien on documente qu'il n'y a rien où renvoyer. L'interface de LLDAP est réservée à `bd-admins` en `two_factor` (AUTH-7) : le seul libre-service d'un membre aujourd'hui est « Mot de passe oublié ? » sur le portail. L'ouvrir aux comptes authentifiés est une ligne d'`access_control` — LLDAP borne déjà un utilisateur ordinaire à son propre profil — et non du code d'ici : l'application N'AUTHENTIFIE PERSONNE (AUTH-1), et lui donner un chemin d'écriture sur l'identité effondrerait le raisonnement entier
- [ ] **Le courriel est le point sensible de la déclaration AUTH-5** — attendu : la raison est écrite, pas seulement le fait. La sortie déclarée de `/api/moi` porte `{login, nom}` et EXCLUT explicitement le courriel (« il reste dans le miroir `utilisateur`, donc dans la seule sauvegarde »). Le montrer à son propriétaire est défendable — c'est le sien —, mais c'est un élargissement de déclaration et non un effet de bord

### Le crédit — le trou mesuré, et ce n'est pas celui qu'on demandait
- [ ] **`contribution` n'a pas d'ORCID, et ne parle pas des annotateurs** — mesuré le 2026-09-07 : la table porte `nom`, `role_id`, `rang` (`database.py`), `tools/crosswalk_depot.py` code en dur `"orcid": None` sur ce chemin, et son sujet est l'auteur de la BD — scénariste, dessinateur. La seule colonne portant un ORCID est `collection.responsables`, un JSON écrit en CLI par `gerer_collections.py`, et qui dit qui GÈRE le corpus
- [ ] **La phrase de `CLAUDE.md` qui justifie la pseudonymisation est donc fausse** — attendu : corrigée ou retirée. Elle affirme qu'« un login ne sert bien aucun des deux buts de la sortie — `agent_type` suffit à l'audit, et l'attribution scientifique a `contribution` avec son ORCID ». C'est ce qui rend `annotateur-N` acceptable, et cela renvoie vers un chemin de crédit qui n'existe pas pour qui annote. Retirer une fausse assurance vaut mieux que la réparer tant que le chemin n'est pas ouvert ailleurs
- [ ] **Une déclaration de crédit est le SEUL fait d'identité que l'application devrait posséder** — attendu : tranché. « Qui vous êtes » est un miroir et appartient à Authelia ; « comment vous voulez être cité » est une déclaration de la personne sur elle-même, qu'aucun annuaire ne sait porter et que personne d'autre n'a qualité pour écrire. C'est aussi ce qui rendrait `annotateur-N` tenable au lieu d'être un pis-aller : on pseudonymise parce que le crédit passe ailleurs — encore faut-il que l'ailleurs existe
- [ ] **Et elle change de nature à la SORTIE** — attendu : écrit AVANT la table, pas après. Une déclaration de crédit est faite POUR partir, là où tout le reste de l'identité est retenu : elle est l'EXCEPTION à `pseudonymes()` et non un cas de plus à retenir. Le cliquet AUTH-5 doit donc la voir sortir et l'avoir déclarée, ce qui est l'inverse de son usage habituel. `personnage_alignement` (A5) montre déjà comment on range un URI d'autorité et comment on le fait sortir

### L'identité collective — tranchée par `AUTH-6` le 2026-09-09
- [x] **Le cas est renvoyé à `AUTH-6`** — 2026-09-07, réponse de l'équipe : « pas décidé, c'est ce qu'il faut trancher ». Aucun compte collectif n'est en service : `utilisateur` ne contient que `chercheur` et `stagiaire`, mesuré le 2026-09-07 sur AUTH-7. Ce qui suit reste écrit ICI parce que la mesure a été faite le jour où la question s'est posée ; rien ne s'engage tant qu'AUTH-6 n'a pas répondu. **AUTH-6 a répondu le 2026-09-09** : des comptes collectifs, dans les deux formes — un login partagé utilisé en même temps, des groupes qui se succèdent —, DÉCLARÉS par `utilisateur.nature` (v26, `58c6e71`). AUTH-6 a construit la DÉCLARATION, pas de registre NOMINATIF : les cases ci-dessous se relisent avec cette distinction (relu le 2026-09-11)
- [x] **SUCCESSIF et SIMULTANÉ ne coûtent pas la même chose, et un seul est atteignable** — attendu : la décision le dit. **Dit par AUTH-6** (case « Un compte COLLECTIF est-il prévu », 2026-09-09) : les deux formes sont prises en connaissance de cause, et l'application ne distinguera jamais deux personnes sous le même login. Un login passé de main en main laisse DÉJÀ une coupe datée (`_identite_reprise`, AUTH-7 `e3e572b` : « on ne l'applique pas, on cesse de la perdre ») ; un registre nominatif permettrait de l'APPLIQUER, et c'est le cas le moins cher. Trois personnes tapant sous le même login la même semaine ne laissent RIEN : l'application reçoit un `Remote-User`, et aucun événement daté n'attribue quoi que ce soit
- [x] **Un registre est une DÉCLARATION, jamais une attribution, et son danger est de ressembler à l'autre** — attendu : son gain est nommé à l'envers de ce qu'on espère. **Construit par AUTH-6** (`58c6e71`), sous la forme de la nature du compte : ANN-5 rend `non_attribuable`, toujours présent même à zéro — « je ne peux pas mesurer » au lieu d'un silence. Il ne récupère pas d'attributions : il fait REFUSER DE RÉPONDRE. Un login collectif rend aujourd'hui l'accord inter-annotateurs muet (AUTH-6 : « n'a plus rien à mesurer »), et ce vide est indistinguable de « personne n'a encore relu » — la forme exacte du défaut qu'AUTH-8 poursuit sur le bandeau de portée vide. Un registre permet de dire « collectif : non mesurable par construction », ce qu'aucun silence ne dira
- [ ] **`pseudonymes()` rend UN `annotateur-N` pour N humains** — attendu : si un registre existe, le nombre est déclarable ; sinon, le fait est écrit là où un lecteur d'artefact peut l'atteindre. AUTH-7 nomme déjà le défaut (« l'export les fond en un seul `annotateur-N` et la chaîne de révision devient fausse ») sans qu'aucun artefact ne le signale à qui le lit. **État au 2026-09-11** : un agent déclaré collectif sort désormais sous `collectif-N` (AUTH-6), ce qui DÉCLARE la nature ; le NOMBRE de personnes derrière reste non déclaré, faute de registre nominatif — c'est ce qui reste de cette case
- [ ] **Le registre serait RETENU de toute sortie** — attendu : rangé dans `CIBLES_RETENUES` (`tools/_commun.py`) avec sa raison, et couvert par le cliquet AUTH-5. C'est une liste de noms de personnes réelles, c'est-à-dire exactement ce que `pseudonymes()` existe pour retirer ; l'oublier en ferait une voie de fuite neuve. Le patron est déjà posé : une table absente des deux ensembles fait ÉCHOUER `test_journal_publie_par_decision`, pour que la retenue soit PAR DÉFAUT et non par décision. **État au 2026-09-11** : aucun registre nominatif n'a été construit, donc cette case reste l'attendu du jour où il le serait. La déclaration de NATURE, elle, est déjà retenue (`utilisateur_nature` dans `CIBLES_RETENUES`, avec sa raison)
- [x] **Outiller le compte partagé rouvre un arbitrage déjà payé** — attendu : assumé par écrit, ou refusé. **Assumé par écrit par AUTH-6** le 2026-09-09 (« une décision prise en connaissance de ce qu'elle coûte ») : le remède n'a pas été d'interdire mais de rendre la nature VISIBLE, et Ctrl+Z est borné à cinq minutes sous un compte déclaré collectif depuis le 2026-09-11 (`ff95ec0`). Le `one_factor` du 2026-09-06 (INFRA-8, AUTH-6) existe PARCE QUE le second facteur obligatoire poussait vers un compte partagé, dont AUTH-6 liste le coût : `undo.py` filtre par agent, donc Ctrl+Z défait le travail d'un collègue ; l'accord inter n'a plus rien à mesurer ; la provenance aplatit les chaînes de révision. Rendre le compte partagé tolérable, c'est cesser de le réparer

## Contexte

**Ce que la pastille porte aujourd'hui**, et c'est le point de départ matériel :
`static/theme.js` injecte `.user-chip` sur les cinq surfaces — une icône, le nom lisible,
un lien de déconnexion vers le portail, et une infobulle qui porte le login ET la liste des
groupes. Cette infobulle est déjà un panneau membre en réduction : elle dit ce que
l'application sait de vous, dans le seul endroit qui n'est pas un `title` près d'être
illisible. Le chantier consiste largement à lui donner une surface.

**Le code coûte peu, et il faut le dire pour que la discussion porte sur le reste.**
`/api/moi` émet déjà l'identité, la portée en compteurs et les groupes ; `_comptes()`
calcule déjà par login les actes au journal A3, les accès explicites et les reprises. Un
panneau membre est ce même calcul restreint à `portee.utilisateur`, plus une modale. Ce
qui coûte, ce sont les pièges ci-dessus — dont trois sont des interdits (n'écris pas le
miroir, ne prends pas la place de l'annuaire, déclare ta sortie) et un seul un choix de
forme.

**Le trou du crédit est arrivé de biais**, comme souvent ici : on cherchait le coût d'une
page de profil, on a trouvé qu'une phrase de doctrine renvoie vers un chemin inexistant.
La pseudonymisation des annotateurs (AUTH-1) se justifie par le fait que le crédit
scientifique passe par un autre canal ; ce canal n'existe que pour qui GÈRE une collection
(`responsables`, avec ORCID, en CLI) et pas du tout pour qui annote. Ce n'est pas un défaut
de la pseudonymisation — elle reste juste — c'est son argument qui est en l'air. Un panneau
membre est l'endroit naturel pour le poser, parce que c'est le seul écran où la personne
parle d'elle-même.

**Pourquoi cette fiche existe alors qu'AUTH-6 et AUTH-7 couvrent déjà les comptes.** Les
deux autres regardent le compte depuis l'administration : qui existe, qui crée, ce qu'une
suppression casserait. Celle-ci le regarde depuis la personne, et c'est la seule qui
s'adresse à quelqu'un sans droits. La correction de placement du 2026-09-07 est exactement
ce constat : mettre le panneau sur `/administration` aurait fait de son public l'inverse du
sien.
