---
chantier: AUTH-6
statut: interrompu
---

# AUTH-6 — le modèle de comptes et de groupes, avant les stagiaires

**Arrêté sur** — le commit `9e594b8`, 2026-09-09 : le cadrage est rendu, les neuf
questions sont tranchées, et **deux constructions sur trois sont faites** — la nature d'un
compte est dans le modèle (`58c6e71` : ANN-5 refuse de mesurer sur un agent collectif, les
sorties le déclarent), et un accès accordé à un login jamais vu le DIT.

**Le défaut réel n'était pas celui que cette fiche annonçait, et il était pire.** Elle
écrivait qu'ANN-5 rendrait « aucun désaccord » sous un login partagé. Sa condition de
re-touche est `agent_précédent != agent` : deux personnes qui se relisent sous le même
login ne produisent donc pas un faux accord, elles SORTENT de l'échantillon. Le taux
portait sur moins de travail qu'on ne croyait, et l'écart n'apparaissait nulle part — le
mode d'échec d'ARCH-2, une mesure qui rétrécit en silence, découvert en écrivant le
correctif de ce qu'on croyait être l'autre défaut.

**Ce que le cadrage change vraiment**, et qui ne se devine pas en lisant les réponses une
par une : le corpus sera annoté **majoritairement sous des identités non individuelles**.
Dix comptes nommés au maximum, pour des dizaines et des dizaines de comptes. ANN-5 et les
chaînes de révision du journal A3 gardent tout leur sens — sur ces dix-là seulement. Le
reste du travail sera attribuable à un GROUPE, jamais à une personne, et c'est une
décision prise en connaissance de ce qu'elle coûte.

D'où la seule chose qui doit absolument être construite : **un compte collectif doit se
DÉCLARER comme tel**. Sans quoi ANN-5 rendrait « aucun désaccord » là où la réponse est
« je ne peux pas mesurer » — le mode d'échec que ce dépôt traque partout, une garde qui
approuve en n'ayant rien vu.

**Ce que le cadrage NE fait PAS**, contre ma première rédaction : il n'invalide aucune
hypothèse d'AUTH-7. Cette fiche avait déjà chiffré le volume le 2026-09-06 — jusqu'à
300 comptes sur cinq ans, par pics de 30, ~20 h de saisie étalées — et conclu que ce
n'était pas lui qui décidait. « Des dizaines et des dizaines » CONFIRME ce chiffre au lieu
de le contredire, et la douleur reste celle qu'AUTH-7 nommait : le PIC, trente personnes
dans la semaine où l'on a le moins de temps.

**Point de départ** — 2026-09-05. Le cadrage appartient à l'utilisateur du dépôt, qui l'a
annoncé et le rendra ; cette fiche note les questions que le CODE pose à ce cadrage, et
deux pièges que le modèle actuel ne signale pas.

**Un premier morceau a été pris le 2026-09-06, parce qu'il bloquait une arrivée**, et il
contraint la suite. `two_factor` partout exigeait de chacun une application
d'authentification sur un téléphone lui appartenant, ce qui poussait vers un COMPTE
PARTAGÉ — dont le coût est invisible ici : `undo.py` filtre l'annulation par AGENT (Ctrl+Z
défait l'action d'un collègue), l'accord inter-annotateurs n'a plus rien à mesurer, et le
journal de provenance aplatit les chaînes de révision. D'où : comptes NOMINATIFS en
`one_factor`, second facteur maintenu pour `bd-admins` et sur `/api/sauvegarde`. Détail et
raisons dans `INFRA-8`. Ce chantier peut le défaire, mais en connaissant ce qu'il paie.

## Reste

### À trancher (hors code — la décision revient à l'équipe)
- [x] Combien de comptes, et lesquels sont NOMMÉS. **Tranché le 2026-09-09.** **Des dizaines et des dizaines** au total, dont **dix au maximum de NOMMÉS**. La conséquence est à écrire noir sur blanc : ANN-5 et les chaînes de révision du journal A3 ne portent que sur ces dix-là. Le reste du corpus sera annoté sous des identités non individuelles, et aucune mesure d'accord n'y a de sens — ce n'est pas une dégradation, c'est le périmètre réel de l'instrument
- [x] Un compte COLLECTIF est-il prévu, et sous quelle forme. **Tranché le 2026-09-09.** **OUI, et dans les deux formes** : un login PARTAGÉ, utilisé SIMULTANÉMENT, et des groupes qui se SUCCÈDENT. Il **coexiste** avec les comptes nominatifs plutôt que de les remplacer, et **écrit partout où ses accès le portent**. La fiche demandait de distinguer le successif du simultané parce qu'un seul est attribuable ; la réponse prend les deux en connaissance de cause, et le remède n'est pas d'interdire mais de rendre la nature collective VISIBLE aux deux mécanismes qui mentiraient en silence (items plus bas). **Ce que l'application ne pourra PAS faire, et c'est la borne du chantier** : distinguer les instances. Elle ne voit que `Remote-User` ; lui donner de quoi séparer deux personnes tapant sous le même login reviendrait à lui faire fabriquer de l'identité, ce qu'AUTH-1 lui interdit. « Ses propres contrôles » porte donc sur le COMPTE, jamais sur la personne devant l'écran
- [x] Quels groupes existent, et ce que chacun signifie en termes de collections. **Tranché le 2026-09-09.** **Plusieurs groupes d'ÉTUDIANTS** — un par cours, chacun avec ses corpus et ses collections —, **plusieurs comptes STAGIAIRES** et **plusieurs comptes DÉMO**. Donc plusieurs comptes collectifs, et non un cas particulier isolé : la nature collective est une CLASSE. Le cloisonnement par cours tombe exactement sur ce que `collection_acces` sait faire, à condition que le principal soit le GROUPE et non chaque login — c'est à cela que les groupes servent
- [x] Ce qui se passe quand quelqu'un CHANGE de groupe en cours de route. **Tranché le 2026-09-09.** **Une personne appartient à UN SEUL groupe à la fois** : changer REMPLACE, rien ne s'accumule. L'accès suit à la requête suivante (les groupes sont relus dans `Remote-Groups`), la provenance NON — les actes déjà journalisés restent attribués à qui les a faits, et c'est voulu. **Attention, le code ne fait pas cette hypothèse** : `Portee.__init__` CUMULE les niveaux de tous les groupes présents. Tant que l'annuaire n'attribue qu'un groupe, cumul et remplacement donnent le même résultat ; le jour où deux groupes coexisteraient par erreur, le cumul serait plus PERMISSIF que le modèle décidé, et rien ne le dirait
- [x] Combien d'administrateurs. **Tranché le 2026-09-09.** **UN seul `bd-admins`** pour l'instant — celui qui court-circuite `collection_acces` et voit tout le corpus (AUTH-4) —, et **deux à trois administrateurs de COLLECTION**. Cette seconde catégorie ne demande aucun code : c'est le niveau `proprietaire` de `collection_acces`, et `peut_administrer()` est déjà distinct de `peut_ecrire()`. La réponse tombe exactement sur la distinction que le modèle porte déjà

- [x] Le second facteur se règle-t-il compte par compte, et selon quoi. **Tranché le 2026-09-09.** **Ni par groupe, ni par collection : on n'y touche pas.** L'état du 2026-09-06 tient — second facteur pour `bd-admins` et sur `/api/sauvegarde`, `one_factor` ailleurs. La raison écrite ce jour-là vaut toujours : aucun cas intermédiaire n'existe encore, et un mécanisme de sécurité sans utilisateur est un mécanisme que personne ne vérifie
- [x] Ou le facteur dépend-il de la COLLECTION plutôt que de la personne. **Tranché le 2026-09-09.** **Écarté avec la précédente** — les deux lectures s'excluaient, et c'est la troisième voie qui l'emporte : ne rien ajouter tant qu'un cas réel ne l'exige pas. À rouvrir le jour où une collection sous embargo ou à base légale non établie entrera dans le corpus (DROIT-1, DEPOT-1)
- [x] L'OUTILLAGE de ce modèle est parti dans `AUTH-7`. **Tranché le 2026-09-09.** Les deux se lisent ensemble, et le cadrage **CONFIRME** ce qu'AUTH-7 avait chiffré le 2026-09-06 plutôt qu'il ne le contredit : jusqu'à 300 comptes sur cinq ans, par pics de 30. Sa conclusion tient donc — ce n'est pas le volume qui a décidé de la bascule vers LLDAP, c'est que le geste cessait d'exiger un shell sur le VPS. Ce qui reste ouvert est ce qu'AUTH-7 nommait déjà sans le chiffrer : le PIC. Trente formulaires dans la semaine où l'on a le moins de temps, et aucun approvisionnement en LOT (import LDIF ou CSV) n'a jamais été évalué
- [x] Le réglage restera-t-il sur le SERVEUR. **Tranché le 2026-09-09.** **OUI pour la POLITIQUE** : éditer `access_control` dans `deploy/authelia/configuration.yml` et redémarrer Authelia reste acceptable, parce qu'elle bouge assez rarement. L'APPARTENANCE, elle, se règle déjà dans l'interface web de LLDAP depuis le 2026-09-07. **Mais la lecture de l'annuaire DEPUIS l'application est décidée par ailleurs** (section suivante) : ce n'est pas la politique qui entre dans l'application, c'est la CONNAISSANCE des comptes

### Les pièges que le modèle ne signale pas
- [ ] Ce que devient un accès dont le GROUPE a été renommé ou supprimé **dans LLDAP** — `collection_acces` stocke une RÉFÉRENCE au nom du groupe, jamais une appartenance : la ligne survit à un groupe qui n'existe plus, et personne ne la relie à rien. **La réponse a CHANGÉ dans la même heure, le 2026-09-09, et les deux états sont gardés parce que le second n'annule pas le raisonnement du premier.** D'abord « on documente que l'application ne le détecte pas » — la branche déjà prise pour les logins jamais vus (AUTH-3), et la seule possible tant que l'application ne lit aucun annuaire. Puis la lecture de l'annuaire a été décidée, ce qui rend la détection POSSIBLE. Attendu : le panneau signale un groupe qui n'existe plus, et **échoue en disant qu'il n'a pas pu vérifier** plutôt qu'en déclarant l'accès mort. **BLOQUÉE derrière la lecture d'annuaire** (case « L'application LIT l'annuaire », zone suivante), noté le 2026-09-10 : l'attendu suppose de savoir ce qui EXISTE dans LLDAP, et l'application n'en lit rien aujourd'hui — mesuré, pas une ligne. Tant que cette décision n'est pas exécutée, cette case n'est pas actionnable, et elle se lisait comme si elle l'était
- [ ] Ce qu'une collection devient quand son unique propriétaire perd son groupe : la base refuse le zéro-propriétaire par un 409, mais ce refus porte sur une SUPPRESSION d'accès, pas sur une appartenance qui s'évapore côté annuaire. **Tranché le 2026-09-09 : `bd-admins` comme recours ne suffit pas, les collections orphelines doivent être SIGNALÉES.** Attendu : un écran ou un contrôle liste les collections dont aucun propriétaire déclaré n'a d'appartenance vivante, et un test joue le scénario entier — le propriétaire perd son groupe, la collection apparaît dans la liste, un administrateur réattribue la propriété. **BLOQUÉE derrière la lecture d'annuaire** (case « L'application LIT l'annuaire », zone suivante), noté le 2026-09-10 : l'attendu suppose de savoir ce qui EXISTE dans LLDAP, et l'application n'en lit rien aujourd'hui — mesuré, pas une ligne. Tant que cette décision n'est pas exécutée, cette case n'est pas actionnable, et elle se lisait comme si elle l'était. **Et l'écran qui listera ces collections vit en Administration**, par la frontière tranchée dans `COL-2` le même jour : une propriété est un ACCÈS, donc « qui entre » — la Bibliothèque prend les descripteurs, pas les accès
- [x] **Un accès accordé à un login que l'application n'a JAMAIS vu le dit** — fait le 2026-09-09 (`9e594b8`). `_acces_de` rend `jamais_vu` : le panneau des accès marque le login d'un « n'a pas encore ouvert l'application », et la note sous le formulaire a été RÉÉCRITE, sans quoi l'écran se serait contredit à deux centimètres — elle affirmait qu'un login mal orthographié n'ouvre rien « sans le dire », ce qui vient de cesser d'être vrai pour les logins et reste vrai pour les groupes.

  **Le champ ne distingue PAS une faute de frappe d'un arrivant qui n'est pas encore venu**, et c'est la moitié de sa valeur : les deux produisent la même absence, l'application ne peut pas les départager, et prétendre le contraire enverrait chercher la mauvaise panne. Même raison qui a fait réécrire le bandeau de portée vide le 2026-09-06.

  **`None` pour un GROUPE, jamais `False`** — le cœur du chantier. L'application ne lit aucun annuaire (AUTH-1) ; répondre `False` affirmerait « ce groupe existe », ce qu'elle n'a aucun moyen de savoir. C'est la leçon d'AUTH-8, où `None` et `False` ont dû être séparés parce qu'un en-tête ABSENT et un en-tête VIDE arrivaient identiques. La mutation qui remplace `None` par `False` ne fait tomber QUE le test des groupes : la distinction est réellement gardée
- [x] **Le panneau des accès est audité AVEC du contenu dedans** — trou trouvé en relecture, et il était entier. `test_a11y_chargement` visite bien `/administration`, mais la liste des accès vit dans un `<details>` que rien n'ouvre et qui ne se charge qu'au dépliage : AUCUN élément de ce panneau n'était jamais passé devant axe. Le nouvel audit prend un décor DERRIÈRE LE PROXY — sans identité, créer une collection est refusé, donc le panneau se rendrait vide — et attend le marqueur LUI-MÊME plutôt que son conteneur. Éprouvé : une couleur à contraste insuffisant fait échouer l'audit en nommant `.acces-jamais-vu`, en thème sombre seulement

### Ce que le cadrage du 2026-09-09 met à construire

- [x] **La nature COLLECTIVE d'un compte est portée par le modèle, à un seul endroit** — `utilisateur.nature` (v26, `58c6e71`), défaut `nominatif` RÉTROACTIF plutôt que NULL : une nature inconnue obligerait chaque lecteur à décider quoi en faire, et le premier qui traiterait NULL comme « pas collectif » réintroduirait le silence que la colonne ferme. Posée par `PATCH /api/comptes/{login}/nature`, réservée aux administrateurs, et par un sélecteur dans la vue des comptes — sans écran, elle se poserait en SQL, ce qu'AUTH-7 venait de supprimer. Elle ne borde AUCUN droit. ANN-5 rend désormais `non_attribuable` (révisions internes à un login partagé + paires dont un côté est un groupe, retirées des taux), TOUJOURS présent même à zéro, sans quoi son absence se lirait comme une absence de problème ; les sorties rendent `collectif-N` au lieu d'`annotateur-N`, en gardant le numéro de la série commune. Quatre mutations rouges
- [x] **Le rapport décrit SON échantillon, jamais l'instance** — trouvé en relecture le 2026-09-09, et aucun cliquet ne pouvait le voir. `agents_collectifs` publiait tous les comptes collectifs de l'instance alors qu'`accord-inter` est cloisonnable par albums (AUTH-2) : des logins de GROUPES partaient à qui ne lit que ses propres albums. Le cliquet d'AUTH-5 était structurellement aveugle — sa sentinelle n'est pas déclarée collective, donc ce chemin ne s'allumait jamais
- [ ] **L'undo se borne dans le TEMPS pour un compte collectif** — `undo.py` filtre par AGENT, donc sous un login partagé n'importe qui défait l'acte d'un autre par Ctrl+Z. Attendu : `GET /api/undo/prochain` n'offre, sur un agent collectif, que les actes de moins de N minutes. Le TEMPS et non la session, parce que l'application n'a aucune notion de session et ne doit pas s'en fabriquer une (AUTH-1) — et parce que le vrai risque est de défaire ce qu'un collègue a fait il y a une heure, pas il y a trente secondes
- [ ] **L'application LIT l'annuaire, en seule lecture, et l'autorisation n'y touche pas** — décidé le 2026-09-09. Le but n'est pas le diagnostic mais la COMPOSITION : connaître les comptes et groupes existants pour attribuer collections et droits sans deviner un login dans un champ libre. Attendu en trois parties : (a) le chemin d'autorisation continue de ne lire que `Remote-Groups`, requête par requête, et un test le verrouille ; (b) l'application n'authentifie toujours personne ; (c) une panne de lecture dit « je n'ai pas pu vérifier » et ne déclare jamais un accès mort. **Le coût qui reste une fois les mauvais arguments retirés** : un identifiant de service dans l'environnement de l'application, classe de secret qu'elle n'a pas aujourd'hui. L'objection de DISPONIBILITÉ est retirée — Authelia dépend déjà de LLDAP, donc s'il tombe, personne n'est connecté pour consulter l'écran.

  **Cette case est la CLÉ DE VOÛTE de la fiche, relevé le 2026-09-10.** Les deux cases de la zone « Les pièges que le modèle ne signale pas » en dépendent entièrement, et ce chantier ne se referme donc pas par ses cinq cases restantes prises dans n'importe quel ordre : il se referme par celle-ci d'abord. **Ce qu'elle entraîne AILLEURS, et qui n'était écrit nulle part** : le cliquet d'`AUTH-5` (`tests/test_sorties_identite.py`) exige une entrée déclarée par SORTIE, avec sa sorte et sa raison — publier des logins et des groupes que l'application n'a jamais vus en crée de nouvelles ; et `CLAUDE.md` comme `docs/hebergement-securite.md` affirment aujourd'hui que les groupes ne sont jamais stockés et se relisent dans `Remote-Groups` à chaque requête. LIRE un annuaire pour la COMPOSITION est un acte distinct d'AUTHENTIFIER, mais la distinction n'existe nulle part par écrit : sans elle, le prochain lecteur conclura que l'invariant d'AUTH-1 a sauté

### Préparer l'arrivée
- [ ] Un compte stagiaire créé de bout en bout voit un corpus NON VIDE dès sa première connexion — c'est le piège d'AUTH-2, et il est silencieux : la connexion réussit, l'application s'affiche, elle est simplement vide.

  **Une mesure de production a été proposée le 2026-09-10 et NE FERME PAS cette case**, ce qui vaut d'être écrit parce qu'elle en avait l'air. `GET /api/moi` sous `stagiaire` rend `acces.collections: 1` — mais ce champ vaut `len(portee.lecture)`, soit le nombre de COLLECTIONS lisibles, jamais un nombre d'albums. Un stagiaire admis sur une collection VIDE rendrait exactement le même `1`, et son écran serait vide : c'est mot pour mot le piège que cette case décrit. Ce qui la fermerait tient en une requête — `GET /api/albums` sous SON identité, rendant au moins une ligne — ou en un regard sur sa Bibliothèque.

  **Et la mesure a montré autre chose, qui n'est pas dans cette case** : `ecriture: 0`. Un stagiaire qui n'écrit nulle part ne peut pas annoter, ce qui est la raison de sa venue. Ce peut être une phase d'observation voulue ; si ça ne l'est pas, il se heurtera à un 403 sur chaque geste sans que l'écran l'ait prévenu — le client ne reçoit même pas `peut_ecrire`, la garde se posant sur l'ACTE (§ Autorisation par collection). À trancher AVANT l'arrivée, pas après
- [x] `BD_REFERENT_NOM` / `BD_REFERENT_CONTACT` sont renseignés — mesuré le 2026-09-09 SUR LA PRODUCTION en fermant INFRA-9 (session voisine, pas cette fiche) : `GET /api/moi` sous `stagiaire` rend `referent: {nom, contact}`, et le bandeau de portée vide les AFFICHE, vérifié dans un navigateur sous un compte jetable sans aucun accès. C'était l'oubli du 2026-09-06 — fonctionnalité livrée, jamais configurée.

  **Trois réserves, pour ne pas cocher plus large que la mesure.** (a) Elle vaut pour cette instance à cette date, pas pour un déploiement neuf — un `.env` recréé repartirait sans référent, et rien ne le signalerait. (b) `referent` est `null` en LOCAL, aucun décor de QA ne posant ces variables : l'écran qu'on éprouve en développement n'est donc pas celui qu'on sert. (c) L'attendu d'origine était TEMPOREL — « AVANT le premier compte non-administrateur » — et cette partie-là n'est plus vérifiable : `stagiaire` existe déjà. Ce qu'on sait est qu'ils sont posés aujourd'hui, pas qu'ils l'étaient à temps

## Contexte

**L'invariant à ne pas casser** (AUTH-1) : les groupes ne sont JAMAIS stockés, ils sont
relus dans `Remote-Groups` à chaque requête. Conséquence directe et utile — déplacer
quelqu'un d'un groupe à l'autre dans Authelia prend effet à la requête suivante, sans rien
à synchroniser côté application. Conséquence moins visible : `collection_acces` garde une
référence à un NOM de groupe, et rien ne vérifie que ce nom existe encore.

**Ce que le passage d'un groupe à l'autre ne change pas** : les actes déjà journalisés
restent attribués à la personne qui les a faits. C'est le comportement voulu — une
annotation n'est pas moins la sienne parce qu'elle a changé d'équipe — mais cela veut dire
que la provenance nomme des gens qui n'ont plus accès, et c'est exactement pourquoi les
sorties pseudonymisent (`annotateur-N`, AUTH-1).

**Le backend fichier avait une limite non mesurée, et elle a été tranchée sans jamais être
mesurée.** `users_database.yml` convenait à une petite équipe ; « à partir de quel nombre de
comptes l'édition à la main devient-elle le goulot ? » n'a jamais reçu de chiffre et n'en
recevra pas — AUTH-7 a basculé sur LLDAP le 2026-09-07.

**Et le motif n'était pas le volume**, ce qui vaut d'être gardé parce que l'intuition de
cette page allait dans l'autre sens. Le chiffrage d'AUTH-7 conclut explicitement que le
temps de saisie ne justifie pas la bascule : trente arrivants restent trente formulaires.
Ce qui a décidé, c'est que le geste cessait d'exiger un shell sur le VPS — déléguer la
création d'un compte revenait à déléguer un accès serveur. La limite du backend fichier
n'était pas sa CAPACITÉ, c'était QUI pouvait s'en servir.

**Renvoi vers `AUTH-10`, posé le 2026-09-10.** Trois cases de cette fiche atterrissent dans
le code qu'AUTH-10 décrit : celle du compte collectif ouvre `undo.py` — où la branche du
remède A1 attend, le journal portant déjà `avant` et `apres` sur `token_correction` —, et
celles du groupe renommé ou supprimé travaillent la sémantique de `collection_acces`, la
table qu'un quatrième niveau modifierait. AUTH-10 est `à venir` et l'équipe a décidé le
2026-09-10 de ne rien y engager ; y toucher au passage est possible, mais alors DÉCLARÉ.
