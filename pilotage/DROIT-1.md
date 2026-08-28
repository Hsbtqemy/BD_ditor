---
chantier: DROIT-1
statut: livré
---

# DROIT-1 — restreindre par nature de donnée, pas seulement par corpus

**Arrêté sur** — la règle de l'embargo et la frontière du dépôt, commit `3e33fc8`,
28 août. La dernière case du chantier se referme, et sa relecture a trouvé le trou qu'on
cherchait ailleurs : `_regime` ne lisait que `statut_diffusion`, si bien qu'une collection
déclarée `public` publiait ses scans alors que son embargo courait encore.

Le chantier est **livré** : les quatre commits vivent sur `origin/dev`. La question qui
l'avait laissé ouvert (« l'embargo se lève-t-il tout seul à sa date ? ») a été tranchée le
2026-08-28 : **la date RETIENT, elle ne PROMEUT jamais**.

Le chantier a changé de forme en cours de cadrage, et c'est l'apport de la session : la
fiche visait un TIERING INTERNE (« un utilisateur autorisé ne reçoit ni les dérivés ni
l'OCR »). Arbitrage du 2026-08-28 : à l'intérieur de l'instance, `statut_diffusion` ne
borde RIEN. Le travail d'annotation repose sur les images, et border un membre reviendrait
à annuler AUTH-3 pour ces collections. L'axe n'est pas *niveau d'utilisateur*, il est
DEDANS / DEHORS.

## Reste

### La frontière, écrite avant d'être codée
- [x] Le partage n'est pas « enrichissement contre verbatim » mais **CITER contre PUBLIER**, et il passe par la NATURE de l'acte, jamais par un volume — un plafond serait un chiffre qu'on ne saurait pas justifier, et la fiche met elle-même en garde contre le fait de coder une politique qu'on ne connaît pas (DEPOT-1)
- [x] À l'INTÉRIEUR de l'instance, `statut_diffusion` ne borde rien : qui est admis reçoit tout, scans compris. L'annotation repose sur les images, et le cloisonnement entre équipes est l'affaire d'AUTH-2/AUTH-3
- [x] ~~Un utilisateur autorisé sur une collection `restreint` voit l'enrichissement et ne reçoit ni les dérivés d'images ni l'OCR verbatim~~ — **ABANDONNÉ par écrit** avec sa raison : ce serait l'empêcher de travailler. La case est gardée plutôt que supprimée, pour que le raisonnement reste
- [x] La doctrine « décrire, pas imposer » (2026-07-16) est RÉÉCRITE et non contredite en silence : elle décrivait un enforcement laissé à l'entrepôt, elle précise désormais que la déclaration mord là où la donnée QUITTE l'outil — et nulle part ailleurs. Deux doctrines contradictoires dans le même dépôt était le risque nommé par la fiche

### CITER — la figure accompagnée
- [x] `POST /api/figures` rend un zip : le crop, sa légende prête à coller, sa notice JSON. Ce qui manquait n'était pas l'image (le crop existait) mais le LIEN entre l'image et sa référence — une citation défendable est courte, identifiée et ACCOMPAGNÉE, et livrer les trois séparément revient à laisser recréditer à la main
- [x] Le régime ACCOMPAGNE au lieu de bloquer : la légende porte la licence et la base légale, y compris « non établie » quand c'est le cas — la taire ferait passer pour réglé ce qui ne l'est pas, sur l'artefact même qui sort
- [x] Les mentions sont CHOISIES par l'appelant ; l'ordre, lui, ne se choisit pas — il est bibliographique, sinon deux figures d'une même communication porteraient des légendes de forme différente
- [x] Le nom de fichier porte le repère (`pl-3-c2`) et non la clé primaire, avec repli quand la mention `citation` n'est pas demandée
- [x] Citer ne contourne pas AUTH-2 : chaque région passe par l'accesseur gardé. Sans cette garde, la figure devenait le trou par lequel tout le corpus se lit en images

### PUBLIER — le manifeste IIIF
- [x] Seul artefact du dépôt qui émette des URL d'images : les scans ne sortent que d'une collection `public` ET NOMMÉE (`--collection`). Fail-closed, et cela règle sans arbitrage le cas d'un album vivant dans plusieurs collections (AUTH-3)
- [x] `--verbatim` est refusé hors `public`, et le refus renvoie vers le geste qui convient (citer)
- [x] Les Canvas SURVIVENT sans image : la géométrie et l'enrichissement restent publiables — c'est le scénario de la piste A, déposer ouvertement son travail sur un fonds qu'on ne peut pas diffuser
- [x] Un manifeste amputé le DÉCLARE (`requiredStatement`, que IIIF impose d'afficher), et `valider_iiif.py` n'exempte QUE sur cette déclaration : sans la nuance, « retenir » et « oublier » ses images deviendraient indistinguables et la règle cesserait de mesurer quoi que ce soit
- [x] Le crosswalk de dépôt est inchangé : il n'émet que des notices descriptives et porte déjà `access_rights`. Vérifié plutôt que supposé

### Ce qui s'est rejoué au passage
- [x] `GET /api/sauvegarde` et le dépôt ShareDocs passent aux administrateurs. La condition de réouverture écrite le 2026-08-27 (« dès qu'un tiering de droits est effectif ») s'est déclenchée, et `HORS_PERIMETRE` est ce qui l'a rendue impossible à oublier : la changer supposait de la relire
- [x] La sauvegarde reste ENTIÈRE et change de public : une sauvegarde partielle ne restaure pas une instance, l'argument d'août tient toujours
- [x] La surcharge par album est ABANDONNÉE par écrit, et la raison n'est plus celle qu'on aurait donnée en juillet : depuis AUTH-3 un album vit dans plusieurs collections, il n'y a plus de défaut unique à surcharger. Le besoin réel se traite en constituant deux collections
- [x] Une mutation a d'abord été lue ROUGE à tort : `-k sauvegarde` ne collectait aucun test, et pytest sort non-nul pour cette raison. La garde n'était pas vérifiée du tout. Le harnais de mutation contrôle désormais la COLLECTE avant de conclure
- [x] Le harnais de mutation exige désormais DEUX conditions avant de conclure : que le filtre `-k` collecte des tests, et que le test soit VERT avant la mutation. Trois faux signaux dans la journée, tous de la même famille — conclure d'un code de retour non nul sans regarder POURQUOI il l'était. C'est le défaut que la mutation corrige chez les tests, retourné contre l'outil qui la mesure
- [x] Quatorze gardes vérifiées par mutation sous ce harnais (onze serveur, trois interface)

> **Ce que la relecture a trouvé (2026-08-28)** — un écart, sur une suite verte, et c'est
> la fuite « par la bande » qu'AUTH-2 avait déjà rencontrée sur les attributs d'un objet
> partagé. Un album vit dans PLUSIEURS collections depuis AUTH-3 ; à défaut de
> `collection_id` explicite, la légende créditait la plus ancienne — sans filtre de portée.
> Elle exportait donc le NOM, la licence et la base légale d'une étude qu'on n'a pas le
> droit de voir, dans un artefact qui QUITTE l'instance. Corrigé : la collection créditée
> est choisie parmi celles qu'on lit, et `figure.py` reçoit un ensemble d'ids plutôt qu'une
> `Portee` — la règle reste écrite dans `autorisation.py`, comme pour `lexique_resume`.
- [x] La collection créditée dans une légende est une qu'on LIT (relecture du 2026-08-28)

### L'interface
- [x] La Visionneuse offre l'export de figure sur la région sélectionnée, à côté de la CITATION qu'on vient de lire : c'est là qu'on décide de citer
- [x] Le sélecteur de mentions est servi par `GET /api/figure/champs` et non recopié dans le JS — deux listes qui divergent produiraient une légende amputée sans rien signaler. Un test E2E compare l'écran à ce que la route annonce
- [x] Un PANIER plutôt qu'un export immédiat : une communication a besoin de plusieurs figures, et une modale ouverte empêcherait de sélectionner la région suivante
- [x] Le bouton d'export n'apparaît QUE si le panier est garni — un bouton permanent sur un panier vide promet une action qui n'aboutit pas
- [x] Le nom du zip vient du serveur (`Content-Disposition`) : le recomposer côté client ferait diverger deux horodatages pour un seul export
- [x] L'écran est audité par axe (WCAG 2.1 AA), thèmes sombre et clair, panier garni et modale ouverte
- [x] Quatre comportements d'interface vérifiés par MUTATION. Le premier jet en laissait un VERT : le test lisait l'attribut `hidden` du HTML statique, donc passait même si le code cessait de le piloter. Corrigé en vérifiant que vider le panier REMASQUE le bouton — un état ne se prouve qu'en le faisant changer

### L'embargo — la date retient, elle ne promeut jamais
> Trouvé en codant la règle : `_regime` ne lisait que `statut_diffusion`. Une collection
> déclarée `public` dont l'embargo courait encore **publiait ses scans**, et l'état était
> atteignable — `gerer_collections.py` pose `--statut` et `--date-embargo` séparément. La
> déclaration que le chantier venait de rendre opposable était contournée par le champ
> censé la préciser.
- [x] La question est tranchée par ce que l'outil IGNORE : il ne sait pas POURQUOI l'embargo existe. Un délai qu'on s'est donné (soutenance, accord d'éditeur) se lève de soi-même ; un délai imposé par un ayant droit ne se lève pas — son échéance dit que la contrainte a couru, pas que les droits sont à nous. Le champ qui trancherait, c'est `base_legale`, vide par construction (DEPOT-1) : publier sur la foi d'une date serait la politique inventée contre laquelle la fiche met en garde
- [x] Une collection `public` dont l'embargo COURT ne fait pas sortir ses scans : la date est plus restrictive que le statut, donc la date gagne. Fail-closed, dans la seule direction qui ne peut pas nuire
- [x] Une collection `embargo` dont la date est ÉCHUE ne devient pas publiable pour autant : la passer en `public` est un ACTE, avec quelqu'un derrière
- [x] Le manifeste amputé ne se dit pas `public` : une déclaration qui annonce « régime : public » tout en retenant ses images se contredit elle-même, et le lecteur n'a aucun moyen de savoir quelle moitié croire — c'est le message qui ment, déjà attrapé une fois sur AUTH-3
- [x] Le message ne promet la sortie automatique QUE si elle aura lieu. Trouvé en relisant du code écrit dans l'heure : « les images sortiront d'elles-mêmes une fois la date passée » était annoncé pour TOUT embargo en cours — vrai d'une collection `public`, faux d'une `embargo`, qui restera `embargo` à l'échéance
- [x] Une date ILLISIBLE retient elle aussi, et le dit : le champ est du texte libre, rien ne l'impose à l'écriture, et une faute de frappe ne doit ni ouvrir la porte ni passer pour une décision
- [x] Ne rien faire n'est pas se taire : une échéance dépassée est SIGNALÉE là où quelqu'un s'apprête justement à publier (générateur de manifestes), sur l'écran Collections et dans les deux vues de `gerer_collections.py`. Un embargo échu que personne ne remarque garde un corpus fermé par INERTIE — ce qui trahit l'orientation open-science aussi sûrement qu'une fuite trahit les droits
- [x] L'état est dérivé à UN SEUL endroit (`database.etat_embargo`, jamais stocké, même doctrine que le numéro éditorial), lu par l'écran ET par l'export : deux lectures divergentes du même champ finiraient par se contredire à l'écran
- [x] La bascule à l'échéance reste à l'entrepôt, à qui la date est transmise (`dates[Available]`) — et `docs/crosswalk-depot.md`, qui l'écrivait déjà, est RÉÉCRIT plutôt que contredit en silence
- [x] Treize gardes d'embargo vérifiées par mutation, dont la borne du jour même (« jusqu'au 3 » est fini LE 3, pas le 4) : un `<` mis pour un `<=` serait passé inaperçu

### La frontière du dépôt — deux services Huma-Num, deux côtés
> Précision apportée par le cadrage, et le dépôt ne l'écrivait nulle part : ShareDocs et
> Nakala ont le même opérateur, ce qui les fait confondre. L'axe est **vivant / figé**.
- [x] **ShareDocs est le stockage VIVANT** — modifiable, appelable à tout moment, un espace de travail où les ressources vivent sans question de droits. Y déposer n'est pas PUBLIER, et le régime n'y borde rien
- [x] La docstring de `POST /api/sharedocs/deposer-sauvegarde` disait que la route « fait SORTIR la base de l'instance », ce qui plaçait ShareDocs du côté DEHORS. Corrigée : la garde administrateur reste, mais pour ses deux vraies raisons — sauvegarder est un geste d'exploitation, et l'application ne contrôle pas le partage du dossier d'arrivée
- [x] **Nakala est l'entrepôt du FIGÉ** — traité, nettoyé, déposé, il ne bouge plus. C'est là que la déclaration mord, et on y dépose d'abord le manifeste et ses Canvas, bien plus que les planches
- [x] Le manifeste sans images cesse d'être présenté comme un manque à corriger : c'est la forme NORMALE du dépôt. Le message concluait « déclarez la collection `public` si vous en avez le droit », ce qui faisait de la forme attendue une déficience
- [x] Ce qui est figé doit être DATÉ : le manifeste était le seul artefact de la chaîne sans date (les notices posent `genere_le`, la figure citable `date_export`). Deux dépôts du même album à un an d'intervalle étaient indistinguables — et l'entrepôt garde les deux
- [x] La DÉCLARATION DE DROITS du `requiredStatement` est datée (« Constat du … »). Figée, « régime : restreint » l'affirmerait encore une fois la collection passée `public` : intemporelle, l'assertion devient fausse sans que personne mente
- [x] Trois gardes de datation vérifiées par mutation, dont « la même date des deux côtés » — deux horodatages pour un seul export divergeraient

### Ce qui reste hors périmètre, écrit
- [x] ~~Borner le lot de `POST /api/figures`~~ — **ABANDONNÉ par écrit le 2026-08-28**, avec sa raison. `_figure_zip` construit le zip entier en mémoire puis `getvalue()` en fait une seconde copie : le nombre de régions n'est borné par rien (seule `taille` l'est, à 2000 px). Arbitrage du user : la fonction ne sera pas très sollicitée, et un gros export supposera une bonne raison — un plafond protégerait d'un usage qu'elle n'aura pas en gênant celui qu'elle aura. Le FLUX (`StreamingResponse`) a été examiné et écarté avant même le plafond : les en-têtes `200 OK` partant avant la première figure, un 404 d'AUTH-2 sur la quarantième région deviendrait un téléchargement TRONQUÉ au lieu d'un refus — on échangerait une garde contre de la mémoire. À rouvrir seulement si un incident le demande
- [ ] La base légale reste une question ouverte (DEPOT-1) : le MÉCANISME est là, la POLITIQUE non. Restreindre selon une règle qu'on ne connaît pas serait coder une politique inventée

## Contexte

Deuxième niveau de l'arbitrage du 2026-08-27 : le cloisonnement porte à la fois sur le
corpus (AUTH-3) **et** sur la nature de la donnée. C'est la seule combinaison qui permet
d'inviter quelqu'un sur un fonds sous droits tout en déposant ouvertement son
enrichissement — le scénario même de la piste A.

Le vocabulaire est déjà en base depuis la v14 (`statut_diffusion`, `date_embargo`,
`licence_defaut` avec sa note « tier ouvert »), et le dictionnaire décrit déjà le tiering.
Ce chantier ne conçoit donc presque rien : il rend exécutoire ce qui n'est aujourd'hui que
déclaratif.

**Attention à la doctrine, qui dit l'inverse pour de bonnes raisons.** Décision du
2026-07-16 : « décrire, pas imposer » — ces champs déclarent un régime, l'application ne
l'impose pas, l'enforcement restant au portail d'auth et à l'entrepôt. Ce chantier
RENVERSE ce choix pour l'accès en lecture à l'intérieur de l'outil. Il faut donc le
trancher explicitement et le réécrire dans `docs/dictionnaire-metadonnees.md`, sinon deux
doctrines contradictoires cohabiteront dans le même dépôt.

Dépend de **DEPOT-1** dans les faits : restreindre selon une base légale qui n'est pas
établie, c'est coder une règle qu'on ne connaît pas encore.
