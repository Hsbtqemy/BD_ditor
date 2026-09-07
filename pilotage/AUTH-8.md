---
chantier: AUTH-8
statut: à venir
---

# AUTH-8 — « aucun groupe » recouvre deux situations, et le code les écrase

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
- [ ] `autorisation` distingue l'en-tête ABSENT de l'en-tête VIDE, sans changer le contrat
      de `groupes()` qui rend une liste — l'information « l'en-tête n'est pas venu » voyage
      à part, et un appelant qui l'ignore continue de fonctionner comme avant
- [ ] Le mono-poste est INCHANGÉ : sans `BD_AUTH_PROXY`, aucun en-tête n'est lu et la
      question ne se pose pas. Attendu : aucune des deux nouvelles situations ne peut
      apparaître hors proxy, vérifié par un test
- [ ] `GET /api/moi` publie de quoi trancher, dans le bloc `acces` qui porte déjà le
      diagnostic — et rien de plus : c'est le seul endroit où la liste des groupes sert

### Le dire, sans revenir au sur-diagnostic
- [ ] La ligne technique du bandeau dit l'une de TROIS choses selon l'état réel, et chacune
      reste une observation vérifiable — pas une cause supposée. « Aucun groupe reçu » ne
      doit subsister que là où c'est encore la seule chose qu'on sache
- [ ] Le cas « le proxy ne recopie pas les groupes » est le seul des trois qui appelle une
      réparation : il se distingue à l'écran de celui qui n'en appelle aucune, sinon ce
      chantier n'aura servi à rien
- [ ] Les tests couvrent les TROIS états par leurs en-têtes, y compris `Remote-Groups`
      envoyé VIDE — un cas qu'aucun test actuel ne produit, et sans lequel le nouveau code
      serait vert sans jamais être exercé

### Ce que la doctrine doit cesser de dire
- [ ] `CLAUDE.md` remplace sa mention « non fait » par le résultat, et la phrase qui annonce
      l'ambiguïté comme indépassable disparaît — elle était vraie du code, jamais du
      protocole

## Contexte

**Ce chantier ne rouvre pas le sur-diagnostic, il le rend légitime.** La formulation posée
le 2026-09-07 — rapporter une observation, jamais expliquer une cause — reste la bonne
règle. Ce qui change, c'est que l'observation devient plus fine : on ne dira pas « c'est le
proxy » parce qu'on le suppose, on le dira parce que l'en-tête manque alors qu'Authelia
l'aurait posé.

**Et le bandeau reste destiné à qui est BLOQUÉ.** Les trois formulations vivent dans la
ligne technique, sous le pli, avec le reste qui parle en français à quelqu'un qui n'y peut
rien. Ajouter un état ne doit pas ramener du jargon au-dessus du pli.

**Pourquoi ça vaut la peine, alors que le cas est rare.** Un proxy qui pose `Remote-User`
sans `Remote-Groups` rend TOUS les accès par groupe silencieusement inopérants. Les
personnes concernées se connectent correctement, voient une application vide, et le seul
indice disponible aujourd'hui est un message qui dit la même chose que pour un simple
défaut d'accès. C'est exactement la panne qu'AUTH-1 voulait rendre distinguable, et elle ne
l'était qu'à moitié.

**Voisinage.** AUTH-1 (les trois situations, et le libellé réécrit le 2026-09-07), AUTH-2
(`Remote-Groups` relu à chaque requête, jamais stocké), INFRA-11 (le contrôle du fichier
des comptes, obligatoire pour la manipulation de la première zone), INFRA-8 (le parcours
d'un compte neuf).
