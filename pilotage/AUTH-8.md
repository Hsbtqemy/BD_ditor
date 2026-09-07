---
chantier: AUTH-8
statut: interrompu
---

# AUTH-8 — « aucun groupe » recouvre deux situations, et le code les écrase

**Arrêté sur** — 2026-09-07, `a7afa30` : **le code ne les écrase plus, et le titre de
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

Le message d'origine d'AUTH-1 disait donc vrai dans UN des deux cas — précisément celui que
l'application ne savait pas isoler.

## Reste

### Établir le fait plutôt que le déduire
- [ ] La table ci-dessus est CONFIRMÉE sur l'instance et pas seulement lue dans les
      sources : un compte de test sans `groups:`, et la réponse de
      `/api/authz/forward-auth` interrogée depuis le conteneur Caddy montre
      `Remote-Groups:` présent et vide. Lire un dépôt n'est pas mesurer un déploiement —
      et Caddy a été lu sur `master`, pas sur le tag de `caddy:2-alpine`
- [ ] La procédure d'ajout du compte de test passe par `deploy/verifier_comptes.py`
      (INFRA-11) : c'est ce contrôle qui manquait le 2026-09-06, quand la même manipulation
      a coupé le portail six minutes

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
- [ ] Le bandeau NOMME les quatre situations mais ne se déplie d'office que pour la seule
      panne CERTAINE — l'absence d'identité. Distinguer à l'écran et déplier d'office sont
      deux décisions prises sur deux degrés de certitude différents, et la seconde attend
      la première case de cette fiche. Le jour où la mesure sur l'instance confirme la
      table, `test_le_bandeau_ne_se_deplie_d_office_que_pour_une_vraie_panne`
      (`tests/test_e2e_a11y.py`) est l'endroit qui exigera le second cas — il porte déjà
      la consigne dans sa docstring

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
