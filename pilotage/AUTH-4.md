---
chantier: AUTH-4
statut: livré
---

# AUTH-4 — le référent d'un espace : nommer l'administrateur plutôt que le taire

**Arrêté sur** — le chantier entier, commit `78d492a`, 31 août : le référent de collection
(v25) et celui d'instance, la déclaration d'administration dans le panneau des accès, et le
bandeau de portée vide qui nomme enfin quelqu'un. `autorisation.py` n'est pas dans le diff.

**Ce que la relecture a trouvé, sur une suite verte.** Trois défauts, tous de la même
famille : un écran qui parle d'autre chose que de ce qu'il montre.

1. **Le référent n'était lisible que du propriétaire** — c'est-à-dire de celui qui venait
   de l'écrire. `colDetail` s'arrête net pour qui n'administre pas (« seul un propriétaire
   voit et modifie la liste des accès ») et mon champ vivait sous ce `return`. J'en avais
   même écrit la justification : « désigner un interlocuteur engage la collection
   entière ». C'est vrai de DÉSIGNER, et je l'avais laissé gouverner LIRE — la distinction
   qu'AUTH-3 avait pourtant déjà faite entre `peut_ecrire` et `peut_administrer`.
2. **« En plus des accès ci-dessus »** dans la note d'administration, alors que le
   participant n'a aucune liste sous les yeux : un renvoi à ce qui n'est pas là.
3. **Le nom du référent passait à la ligne** dans le bandeau. `.portee-vide strong` visait
   le titre, seul `strong` du bloc jusqu'ici ; le second l'a hérité, et `display:block` a
   coupé « Référent de cette instance : X — contact » en trois. Aucun audit ne pouvait le
   dire : axe vérifie le contraste et les rôles, pas le sens d'une phrase découpée.

**La leçon, écrite dans `CLAUDE.md`** : une garde d'interface se pose sur l'ACTE, jamais
sur l'écran qui le contient. Le serveur distingue sept questions, le client n'en reçoit
qu'une (`administrable`) — tout ce qu'on ajoute dans un panneau gardé hérite donc de sa
garde par défaut et non par décision. L'erreur échoue en se FERMANT : elle ne casse aucun
test, et une revue de sécurité l'approuve. Le cliquet de `test_autorisation.py` ne couvre
pas ce cas — il exige qu'une ROUTE ait été tranchée, rien n'exige qu'un bloc d'écran dise
quelle question il pose.

**Point de départ** — fiche ouverte le 2026-08-28 au fil d'une conversation de conception,
avant tout code. Le constat : un administrateur (`bd-admins`) lit et écrit toute
collection **sans jamais y figurer**. `clause_album()` renvoie `"1", []` quand la portée
est totale — la requête ne consulte pas `collection_album`, et `collection_acces` ne porte
aucune ligne le concernant, sur aucune collection. Son accès n'est donc pas un droit
accordé, c'est un court-circuit en amont de la table.

Ce n'est pas un défaut : c'est la vérité de tout système auto-hébergé, et il télécharge
`GET /api/sauvegarde` de toute façon. Mais entre « ce pouvoir est inévitable » et « ce
pouvoir est invisible » il y a un écart, et c'est le seul qu'on puisse fermer. Le chantier
ne retire donc rien à personne : il donne un **visage** à un pouvoir qui n'en a pas.

## Reste

### Arbitrages
- [x] Qui désigne le référent est tranché : le propriétaire de la collection (il choisit son interlocuteur, au risque de nommer quelqu'un qui n'a aucun pouvoir sur l'instance) ou l'administrateur lui-même (exact, moins souple). Les deux se défendent, un seul se code
- [x] Ce qu'on stocke est tranché : un login seul ne permet d'écrire à personne. Nom + moyen de contact, ou renvoi vers une page d'instance
- [x] Le sort de `collection.responsables` est tranché : le patron convient (JSON `[{nom, role, orcid}]`, `role` contrôlé-ouvert) mais le champ est SCIENTIFIQUE — il porte un ORCID et il part au dépôt Nakala, où un référent technique n'a rien à faire. Réutiliser ou créer, pas les deux
- [x] L'existence d'un référent d'instance PAR DÉFAUT (variable d'environnement) est tranchée : c'est le seul qui puisse s'afficher à qui n'a encore aucune collection — donc le seul qui serve le bandeau de portée vide, qui est pourtant le cas le plus criant

### Le fait à déclarer
- [x] Le panneau des accès d'une collection cesse de mentir par omission : il déclare que les administrateurs de l'instance lisent et écrivent toute collection. Aujourd'hui `_acces_de()` ne lit que `collection_acces` — la liste affiche trois noms là où quatre personnes lisent, et l'écran protège soigneusement cette liste au motif que « la liste des membres d'une étude est une donnée sur des personnes » (`static/corpus.js:684`)
- [x] Le bandeau de portée vide nomme un destinataire : `static/theme.js:232` envoie déjà une personne BLOQUÉE « demander un accès à un administrateur de l'instance », sans lui dire à qui s'adresser. C'est l'endroit où un référent sert vraiment — avant le panneau des accès, qui n'est vu que par des gens que rien ne bloque
- [x] Les noms de groupes de `BD_AUTH_ADMIN_GROUPS` sortent par une route (le bloc `acces` de `GET /api/moi` est le candidat) : ce ne sont pas des secrets — ils sont en clair dans `deploy/docker-compose.yml` — mais aucune route ne les dit, si bien qu'une personne admise ne peut pas même déduire que le groupe existe

### Vérifications
- [x] `autorisation.py` n'apparaît pas dans le diff du chantier : un référent est une ADRESSE et non un droit. S'il y entre, c'est qu'on a glissé vers le cloisonnement entre administrateurs, écarté ici
- [x] Le cas du référent périmé est documenté et assumé : un référent qui a quitté `bd-admins` reste affiché, parce que l'application ne connaît les groupes que de la personne qui frappe, à l'instant de sa requête (AUTH-1). L'appartenance d'un TIERS lui est structurellement invérifiable — la déclaration est donc déclarative, et le dire vaut mieux que le laisser découvrir

## Contexte

**Deux lectures de « un administrateur dédié à tel espace », et une seule tient.**

*Comme adresse* — un référent est une propriété de la **collection**, jamais de
l'administrateur : l'application ne stocke aucune appartenance de groupe (invariant
AUTH-1), elle ne lit `Remote-Groups` que pour la personne présente. Un champ, un
affichage, et la zone qui décide « qui voit quoi » reste intacte. C'est le critère de
réussite du chantier, d'où la case de vérification sur `autorisation.py`.

*Comme barrière* — « A administre la collection 1, B la 2, et A ne voit pas la 2 » : cher,
et surtout FAUX. Les deux gardent `GET /api/sauvegarde`, entière par décision de DROIT-1
(« une sauvegarde partielle ne restaure pas une instance »), plus le fichier SQLite et le
shell. On afficherait une garantie qu'on ne peut pas tenir, ce qui est pire que de ne rien
afficher. **Écarté avant d'être commencé** — et c'est la raison d'être de la case de
vérification : le glissement se ferait sans qu'on le décide.

**Ce que le chantier suppose déjà fait, et qui l'est.** Le code refuse déjà de confondre
un administrateur et un propriétaire, dans les deux sens : le badge de l'écran Collections
affiche « Administrateur » et jamais « Propriétaire », parce que « le dire à un
administrateur lui ferait croire à un lien personnel avec une collection qui n'est pas la
sienne » (`static/corpus.js:690`) ; un administrateur qui crée une collection n'en devient
pas propriétaire (`main.py:2560`) ; et la garde du dernier propriétaire porte sur l'ÉTAT
et non sur l'acteur, si bien qu'un administrateur ne peut pas évincer un propriétaire d'un
seul geste — il doit d'abord en désigner un autre, ce qui laisse deux événements
`lien`/`delien` au journal. AUTH-4 continue cette ligne : il ne crée pas la distinction,
il la rend LISIBLE à celui qu'elle protège.

**La garantie existe déjà, elle est juste illisible.** Chaque fois qu'un administrateur
entre dans une collection, `evenement.agent` le nomme — le journal A3 enregistre l'acte,
append-only, avec son avant/après. Mais aucune surface ne le RESTITUE : le propriétaire
d'une collection ne peut pas voir QUAND l'administrateur est entré, seulement savoir qu'il
le peut. Son contre-pouvoir réel dépend donc d'une surface d'audit qui n'existe pas. C'est
un chantier voisin et distinct, non ouvert à ce jour ; AUTH-4 tient sans lui, et gagnerait
beaucoup avec.

> **Correction du 2026-08-31.** La phrase d'origine disait « AUCUNE route HTTP ne lit
> `evenement` : les seuls `SELECT` du dépôt sont dans `undo.py` ». C'est faux, et
> l'énumération le montre : `accord_inter.py:50` lit `evenement`, et
> `GET /api/analyse/accord-inter` (`main.py:3635`) le sert — il rend `auteurs`, une liste
> de LOGINS d'annotateurs, plus les paires et les points de divergence, chacun nommant
> deux personnes. Deux outils d'export le lisent aussi (`tools/metadonnees_collection.py`
> déverse la table entière en `evenement.csv` ; `tools/description_collection.py` embarque
> le bloc accord-inter et ses logins). La CONCLUSION tient quand même, et c'est pourquoi
> elle est conservée telle quelle : `accord-inter` mesure l'accord entre annotateurs, pas
> les entrées d'un administrateur, et il n'existe toujours aucune surface qui montre à un
> propriétaire ce qui s'est passé chez lui. Mais l'affirmation était un inventaire fait de
> MÉMOIRE au lieu d'être fait en énumérant ce qui lit la table — exactement le reproche
> qu'AUTH-1 s'adresse à lui-même (cf. [AUTH-1](AUTH-1.md), § voies de sortie).

**`à venir` plutôt que `différé`** : rien ne bloque techniquement, aucun autre chantier
n'a besoin d'aboutir d'abord. Les arbitrages ci-dessus deviendront simplement plus faciles
à trancher à mesure que l'usage multi-utilisateur devient réel (piste C) — on saura alors
qui écrit à qui, et pourquoi. Ouvrir maintenant sert surtout à ce que le raisonnement ne
reste pas dans une conversation.
