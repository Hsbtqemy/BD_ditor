---
chantier: DROIT-1
statut: différé
---

# DROIT-1 — restreindre par nature de donnée, pas seulement par corpus

**Point de départ** — mis en attente derrière AUTH-2. Le vocabulaire existe déjà en base ;
rien ne le fait respecter.

## Reste

- [ ] Le tier d'une donnée est explicite : enrichissement (annotations, tags, lemmes, lexique) d'un côté, scans et OCR verbatim de l'autre — la frontière est écrite avant d'être codée
- [ ] `collection.statut_diffusion` (`public` | `embargo` | `restreint` | `prive`, déjà en base) et `date_embargo` sont RESPECTÉS à la lecture, et pas seulement déclarés
- [ ] Un utilisateur autorisé sur une collection `restreint` voit l'enrichissement et ne reçoit ni les dérivés d'images ni l'OCR verbatim
- [ ] La restriction tient aussi hors UI : exports, manifeste IIIF, route `/derivatives`, crop de région
- [ ] La surcharge par album annoncée dans le dictionnaire est implémentée, ou explicitement abandonnée par écrit

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
