---
chantier: AUTH-8
statut: interrompu
---

# AUTH-8 — « aucun groupe » recouvre deux situations, et le code les écrase

**Arrêté sur** — 2026-09-09, mesure sur l'instance, **sans commit de code** (le dernier
reste `a7afa30`) : **la table lue dans les sources est FAUSSE pour ce déploiement**, et la
branche qu'elle justifiait accuse à tort. Un compte sans aucun groupe ne reçoit pas
`Remote-Groups` VIDE — il ne le reçoit pas du tout, et le bandeau lui annonce donc « les
accès par groupe sont sans effet — à vérifier côté proxy » alors que rien n'est cassé. On
le sait, et c'est la première ligne du relevé qui le prouve : `stagiaire`, mesuré dix
minutes plus tôt, rend `groupes: ["stagiaires"]` et `entete_groupes: true`. La recopie
fonctionne. Détail en § La mesure. Trouvé en fermant une case d'INFRA-9.

**État antérieur — 2026-09-07, `a7afa30`** : **le code ne les écrase plus, et le titre de
cette fiche est désormais au passé.** `autorisation.entete_groupes_recu()` distingue
l'en-tête ABSENT de l'en-tête VIDE, `GET /api/moi` publie la différence dans
`acces.entete_groupes`, et la ligne technique du bandeau nomme QUATRE situations au lieu
de trois — dont une seule appelle une réparation.

**Ce qui reste n'est pas du code, c'est une MESURE**, et c'est la vraie leçon de ce
chantier. La table de correspondance en tête de cette fiche est lue dans les sources
d'Authelia `v4.39.22` et de Caddy ; lire un dépôt n'est pas mesurer un déploiement. D'où
un arbitrage à DEUX DEGRÉS plutôt qu'un seul : l'écran NOMME les quatre situations —
aucune ne demande de certitude, ce sont des faits de fil —, mais il ne se déplie d'office
que pour la panne qu'on SAIT établir. Distinguer et conclure ne coûtent pas la même
preuve, et les mélanger aurait refait l'erreur du 2026-09-06 sous une forme plus fine.

**Point de départ** — 2026-09-07, en réécrivant le bandeau de portée vide. Il annonçait
« aucun groupe » comme un réglage de proxy ; on l'a ramené à une observation faute de
pouvoir établir la cause, parce que `autorisation.groupes()` fait
`request.headers.get("Remote-Groups") or ""` — un en-tête ABSENT et un en-tête VIDE y
arrivent identiques.

**La lecture des sources dit que la distinction existe, et qu'on la jette.** Authelia
`v4.39.22`, `handleAuthzAuthorizedStandard` :

```go
if authn.Details.Username != "" {
    ctx.SetResponseHeaderValue(headerRemoteUser, authn.Details.Username)
    ctx.SetResponseHeaderValue(headerRemoteGroups, strings.Join(authn.Details.Groups, ","))
```

`Remote-Groups` est posé **inconditionnellement** dès qu'il y a un login :
`strings.Join([], ",")` vaut `""`, donc un compte sans groupe reçoit l'en-tête **présent et
vide**. Et Caddy le conserve — `CopyResponseHeadersHandler.ServeHTTP` itère sur les champs
PRÉSENTS de la réponse et recopie chaque valeur, vide comprise.

Donc, derrière ce déploiement :

| en-têtes reçus | ce que ça signifie |
|---|---|
| `Remote-User` absent | aucune identité — le `if` d'Authelia ne s'est pas déclenché |
| `Remote-User` + `Remote-Groups` **absent** | le proxy ne recopie pas les groupes : **panne de configuration** |
| `Remote-User` + `Remote-Groups` **vide** | cette personne n'appartient à aucun groupe : **rien à réparer** |

**Cette table a été CONFRONTÉE à l'instance le 2026-09-09, et sa troisième ligne est
FAUSSE ici** (cf. § La mesure). Elle reste écrite telle quelle parce qu'elle dit fidèlement
ce que les sources donnent à lire : c'est l'ÉCART entre les deux qui est le résultat, et le
corriger en silence effacerait la seule chose que ce chantier a apprise.

Le message d'origine d'AUTH-1 disait donc vrai dans UN des deux cas — précisément celui que
l'application ne savait pas isoler.

## Reste

### Établir le fait plutôt que le déduire
- [x] **La table ci-dessus est confrontée à l'instance, et elle est RÉFUTÉE** —
      2026-09-09, compte jetable `essai-sansgroupe` créé dans LLDAP, sans aucun groupe et
      sans accès : `groupes: []` **et `entete_groupes: false`**. L'en-tête n'est pas vide,
      il est ABSENT. La case attendait « présent et vide » et prescrivait de l'observer
      depuis le conteneur Caddy ; la réponse est venue plus tôt sur la chaîne, par
      `GET /api/moi`, et elle dit l'inverse de la prédiction. Lire un dépôt n'est pas
      mesurer un déploiement — c'était l'attendu de la case, et c'est ce qu'elle a rendu
- [x] **La procédure par `deploy/verifier_comptes.py` (INFRA-11) n'a plus d'objet, et ce
      n'est pas un contournement** : ce contrôle garde `users_database.yml`, qui ne
      gouverne plus rien depuis la bascule LLDAP du 2026-09-07. Le compte de test se crée
      dans l'interface web de l'annuaire, laquelle ne peut pas corrompre ce fichier — le
      mode d'échec des six minutes du 2026-09-06 a disparu par CONSTRUCTION. Close par
      disparition de son risque et non par respect de sa consigne, ce qui est écrit pour
      que personne ne rejoue la consigne en croyant à un oubli

### Ce que la mesure oblige à défaire
- [ ] La branche `entete_groupes === false` de `static/theme.js` cesse d'affirmer « les
      accès par groupe sont sans effet » et de renvoyer « côté proxy » : mesuré, cet état
      est celui d'un compte SANS GROUPE, pas celui d'une panne. Elle se replie sur
      l'observation nue — « Aucun groupe reçu. », ce que la branche `null` dit déjà
- [ ] Le test qui verrouille la distinction à l'écran est réécrit AVEC elle : il exige
      aujourd'hui « sans effet » présent sur un cas et absent de l'autre, donc il
      verrouille la phrase fautive et rendrait la réparation ROUGE. Une garde qui tient une
      erreur en place est la forme la plus coûteuse de ce défaut
- [ ] **`CLAUDE.md` porte l'affirmation réfutée, et c'est le plus PRESSANT des quatre** —
      non parce que c'est le plus grave, mais parce que c'est le seul fichier chargé
      d'office dans CHAQUE session, quand cette fiche ne l'est pas. D'ici la réparation,
      une session qui ouvre le dépôt lira la déduction comme un fait établi et pourra
      bâtir dessus sans jamais croiser AUTH-8. Deux choses à corriger au § Autorisation
      par collection : la phrase « qu'un en-tête absent signifie une panne de recopie est
      déduit des sources d'Authelia `v4.39.22` … et lire un dépôt n'est pas mesurer un
      déploiement », et l'annonce des QUATRE situations, dont la troisième — en-tête REÇU
      VIDE — ne se produit pas sur ce déploiement. **La déduction se DATE, elle ne
      s'efface pas** : sa dernière clause a annoncé sa propre réfutation et permis de la
      reconnaître, et c'est la seule chose qui a marché dans ce raisonnement. **Le même
      geste RETIRE le renvoi posé par la case suivante** — dans le même commit, pas après
- [ ] Le renvoi existe dans les DEUX sens, et sa SORTIE se programme en même temps que son
      entrée : tant que `CLAUDE.md` n'est pas corrigé, son paragraphe dit qu'une mesure le
      contredit et pointe ici ; le jour de la correction, on le RETIRE au lieu de le mettre
      à jour. Une note sur l'état d'un AUTRE document ne se répare pas — « une mesure
      contredit ce paragraphe » devant un paragraphe qui a cessé de l'être se lit encore
      très bien, et c'est PLUS difficile à repérer qu'une affirmation fausse, parce que ça
      a l'air prudent. La péremption d'ici est déjà la pire de sa famille : la phrase
      fautive garde tout son SENS, elle est seulement fausse, donc personne ne la relit, et
      aucun contrôle mécanique ne la voit. Y ajouter un avertissement sans date de sortie
      doublerait le défaut au lieu de le border
- [ ] Ce qui reste réellement à mesurer est NOMMÉ : lequel d'Authelia ou de Caddy laisse
      tomber l'en-tête vide — `/api/authz/forward-auth` interrogé depuis le conteneur Caddy
      le dirait, et Caddy avait été lu sur `master` plutôt que sur le tag de
      `caddy:2-alpine`. Cela ne change RIEN à la réparation ci-dessus, l'application ne
      pouvant de toute façon pas distinguer les deux situations ; c'est ce qu'il faudrait
      savoir pour obtenir un en-tête vide, si on le voulait un jour

### Ne plus écraser la différence
- [x] `autorisation.entete_groupes_recu()` distingue l'en-tête ABSENT de l'en-tête VIDE
      sans toucher au contrat de `groupes()` — un test vérifie EXPLICITEMENT que `groupes`
      rend la même liste vide dans les deux cas, parce que c'est la condition posée ici et
      non un effet de bord à constater plus tard
- [x] Le mono-poste est INCHANGÉ : la fonction rend `None` — et non `False`, qui voudrait
      dire « il manque alors qu'il aurait dû venir ». C'est la forme d'`auteur()`, qui rend
      déjà None hors proxy. Vérifié sur les trois jeux d'en-têtes, tous ignorés
- [x] `GET /api/moi` publie `acces.entete_groupes`, et rien de plus. L'égalité EXACTE de
      `test_moi_sans_auth_local_renvoie_null` a bronché sur ce champ — elle existe pour ça,
      et son propre commentaire dit comment la mettre à jour : ajouter la clé, jamais
      relâcher l'égalité

### Le dire, sans revenir au sur-diagnostic
- [x] La ligne technique dit l'une de QUATRE choses — « aucun en-tête d'identité »,
      « Remote-Groups NON reçu », « reçu mais VIDE », « groupes reçus : … » — et chacune
      est vérifiable sur les en-têtes. Ce qui suit le tiret dans le deuxième cas est une
      INSTRUCTION (où regarder), pas une cause affirmée
- [x] Le cas réparable se distingue à l'écran de celui qui ne l'est pas, et le test
      l'exige des DEUX côtés : « sans effet » présent sur l'un, « NON reçu » absent de
      l'autre. Une assertion sur le seul libellé attendu aurait passé si les deux disaient
      la même chose
- [x] Les tests couvrent les QUATRE états par leurs en-têtes. Et le point qui décidait de
      tout a été MESURÉ avant d'être écrit : Playwright transmet bien `Remote-Groups:`
      vide, il ne le supprime pas. S'il l'avait supprimé, le cas « reçu vide » aurait
      rejoué le cas « absent » et le test serait resté vert sans voir l'état qu'il couvre

### Ce que la doctrine doit cesser de dire
- [x] `CLAUDE.md` dit le résultat : l'ambiguïté était celle du CODE, jamais celle du
      protocole. Le passage nomme les quatre situations, la fonction, le champ publié, et
      sépare ce qui est fait de ce qui reste à mesurer

### L'arbitrage à deux degrés, et ce qu'il attend
- [x] **Le bandeau ne se déplie d'office que pour l'absence d'identité, et cette prudence
      est ce qui a limité les dégâts** — vérifié à l'écran le 2026-09-09 sur l'instance,
      `<details>` bien replié pour un compte sans groupe. La case attendait la confirmation
      de la table pour déplier AUSSI sur l'en-tête manquant ; la table ayant été réfutée, ce
      second dépliage ne viendra jamais, et
      `test_le_bandeau_ne_se_deplie_d_office_que_pour_une_vraie_panne`
      (`tests/test_e2e_a11y.py`) garde exactement la règle qu'il faut. **N'avoir pas déplié
      d'office sur un diagnostic non mesuré est ce qui a rendu ce défaut discret plutôt que
      criant** : il fallait ouvrir le pli pour lire l'accusation. L'arbitrage à deux degrés
      a donc payé dans le sens qu'on n'attendait pas — non pas en distinguant mieux, mais en
      n'insistant pas sur ce qu'on croyait savoir

## La mesure, faite — 2026-09-09

La première case de cette fiche demandait de CONFRONTER à l'instance une table lue dans les
sources. C'est fait, et le résultat est l'inverse de la prédiction.

Deux comptes, deux relevés de `GET /api/moi` derrière le proxy réel :

| compte | `groupes` | `entete_groupes` |
|---|---|---|
| `stagiaire` (groupe `stagiaires`) | `["stagiaires"]` | `true` |
| `essai-sansgroupe` (aucun groupe) | `[]` | **`false`** |

Les sources d'Authelia `v4.39.22` posent `Remote-Groups` inconditionnellement dès qu'il y a
un login, et `strings.Join([], ",")` vaut `""` : un compte sans groupe devait donc recevoir
l'en-tête PRÉSENT et VIDE. Il ne le reçoit pas du tout.

**La première ligne est ce qui rend la seconde concluante.** Sans elle, un
`entete_groupes: false` se lirait comme la panne de recopie que cette fiche décrit —
c'est-à-dire exactement ce que le bandeau en dit. Mais `stagiaire` prouve que la recopie
fonctionne sur ce déploiement : quand il y a des groupes, ils arrivent. L'absence n'est
donc pas une panne, c'est la forme que prend le vide.

**Conséquence, et elle est visible à l'écran.** La branche `entete_groupes === false`
affiche « En-tête Remote-Groups NON reçu, alors que Remote-User l'est — à vérifier côté
proxy : les accès par groupe sont sans effet. » Elle s'affiche donc à quelqu'un pour qui
rien n'est cassé, et l'envoie chercher une panne qui n'existe pas. Le bandeau se contredit
d'ailleurs à deux lignes d'intervalle : « Rien n'est cassé » au-dessus du pli, « sans
effet » en dessous.

**Ce qui tombe, c'est la raison d'être du champ.** `entete_groupes` a été créé pour séparer
« aucun groupe déclaré » de « les groupes ne sont pas parvenus ». Mesuré, il ne les sépare
pas : il distingue « a des groupes » de « n'en a pas », ce que `groupes.length` disait
déjà. L'état « reçu mais VIDE » ne se produit pas ici, donc la branche qui le décrit est
morte et celle qui accuse tire sur tout le monde.

**Ce qui NE tombe pas**, et il faut le dire pour que personne ne défasse trop : le défaut
que cette fiche a réparé était réel. `autorisation.groupes()` écrasait bien `None` et `""`,
et les séparer était juste. Ce qui est réfuté est l'INTERPRÉTATION d'un en-tête absent, pas
le fait que le code confondait deux états.

**Et c'est irrécupérable côté application**, quelle que soit la cause : elle ne lit aucun
annuaire (invariant AUTH-1), donc elle ne peut pas savoir si un compte a des groupes. Les
deux situations arrivent identiques sur le fil. C'est le point de départ de cette fiche,
revenu sous une forme plus fine — et c'est la faute du 2026-09-06 rejouée : affirmer une
cause que le code ne peut pas établir. Le commentaire de `theme.js` le disait lui-même, en
toutes lettres, en renvoyant à la case qu'on vient de fermer.

**Une seule mesure, deux cases.** Le bandeau revu après la montée d'Authelia (INFRA-9) et
la table confrontée (ici). Le compte jetable a été créé dans l'interface de LLDAP — le
geste qu'AUTH-7 venait de rendre possible sans SSH, et sans lequel cette mesure aurait
demandé d'éditer `users_database.yml` sur le serveur, ce que la seconde case de cette fiche
entourait justement de précautions.

## Contexte

**Ce chantier ne rouvre pas le sur-diagnostic, il le rend légitime.** La formulation posée
le 2026-09-07 — rapporter une observation, jamais expliquer une cause — reste la bonne
règle. Ce qui change, c'est que l'observation devient plus fine : on ne dira pas « c'est le
proxy » parce qu'on le suppose, on le dira parce que l'en-tête manque alors qu'Authelia
l'aurait posé.

**Et le bandeau reste destiné à qui est BLOQUÉ.** Les quatre formulations vivent dans la
ligne technique, sous le pli, avec le reste qui parle en français à quelqu'un qui n'y peut
rien. Ajouter un état n'a pas ramené de jargon au-dessus du pli — le titre et le corps sont
inchangés, et c'était la condition.

**Pourquoi ça vaut la peine, alors que le cas est rare.** Un proxy qui pose `Remote-User`
sans `Remote-Groups` rend TOUS les accès par groupe silencieusement inopérants. Les
personnes concernées se connectent correctement et voient une application vide. Le seul
indice disponible disait jusqu'ici la même chose que pour un simple défaut d'accès :
c'était exactement la panne qu'AUTH-1 voulait rendre distinguable, et elle ne l'était qu'à
moitié. Elle l'est maintenant à l'écran ; ce qui manque est la mesure qui autoriserait à
en TIRER une conclusion sans qu'un lecteur la tire lui-même.

**Voisinage.** AUTH-1 (les trois situations, et le libellé réécrit le 2026-09-07), AUTH-2
(`Remote-Groups` relu à chaque requête, jamais stocké), INFRA-11 (le contrôle du fichier
des comptes, obligatoire pour la manipulation de la première zone), INFRA-8 (le parcours
d'un compte neuf).
