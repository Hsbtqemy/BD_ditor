---
passe: TOTP — l'administrateur qui perd son téléphone
chantier: AUTH-7
duree: 20 min
derniere: 2026-09-06
---

# QA — le recours au second facteur existe-t-il ailleurs qu'en console

**Le dossier se contredit, et c'est la seule raison de cette passe.** `INFRA-8` écrit que
le parcours d'un compte est « franchissable seul, **appareil perdu compris** ». `AUTH-7`
écrit que réinitialiser un TOTP exige `authelia storage user totp delete`, **console
uniquement**. Les deux ne peuvent être vraies que si « appareil perdu » désignait le compte
PAS ENCORE enrôlé — qui reçoit un lien d'enregistrement, ce qui est le parcours normal de
première connexion — et non le compte DÉJÀ enrôlé dont le téléphone a disparu.

**Ce que ça décide.** Depuis l'arbitrage du 2026-09-06, seuls les `bd-admins` sont soumis
au second facteur. Les seules personnes qui peuvent donc se retrouver dehors sont
exactement celles qui détiennent le recours — et si ce recours est en console, la première
perte de téléphone d'un administrateur seul ferme l'instance à son administration. Le
serrurier enfermé. Ce n'est pas un risque théorique : c'est le mode de panne d'un outil
mono-administrateur, et il arrive un jour de déménagement ou de téléphone volé.

**Pourquoi la passe ne casse rien.** Les deux premières zones n'exigent que de REGARDER un
écran qu'on atteint déjà. On ne perd aucun appareil, on ne supprime rien : la question est
« que propose le portail à ce moment-là », et elle se lit. La zone 3 seule agit, et elle
agit sur un compte d'essai.

**Ne jamais éprouver ceci sur son propre compte d'administration.** Employer `stagiaire`,
promu dans `bd-admins` le temps de la passe et retiré ensuite — c'est le seul compte dont
le blocage ne coûte rien. Un enfermement de vérification est un enfermement quand même.

## Reste

### Ce qui se lit sans rien perdre
- [ ] Le portail affiche l'écran de second facteur pour un compte `bd-admins` DÉJÀ enrôlé, et cet écran est décrit ici en toutes lettres : quels champs, quels liens, quels boutons. Attendu à confirmer : un champ de code, et la question est de savoir si quelque chose d'autre l'accompagne
- [ ] **Un chemin « appareil perdu » est proposé, ou il ne l'est pas** — c'est LA case de cette passe, et les deux réponses sont des résultats. Attendu : soit un lien de réinitialisation / d'enregistrement d'un nouvel appareil, soit un champ de code seul, auquel cas le recours est en console et le trou est confirmé
- [ ] Le compte `stagiaire`, promu `bd-admins` mais SANS appareil enrôlé, se voit bien proposer l'enrôlement — et non un mur. C'est le parcours qu'`INFRA-8` a éprouvé ; le rejouer ici sépare les deux cas que la contradiction confond, au lieu de supposer lequel avait été testé

### Si un chemin de secours existe, il faut savoir ce qu'il exige
- [ ] Le parcours de secours va jusqu'au bout **sans l'ancien appareil** : un lien qui redemande un code du téléphone perdu n'est pas un recours, c'est le même mur avec une porte peinte dessus
- [ ] Il passe par le **notifier**, et le notifier fonctionne. C'est le même chemin que la réinitialisation de mot de passe (`jwt_lifespan: 15 minutes`), donc il dépend du courriel — ou du repli `filesystem` si `SMTP_ADRESSE` est vide. Un recours qui repose sur une remise de courriel non éprouvée n'est pas éprouvé. Croise la case ouverte d'`INFRA-9`
- [ ] Le délai de 15 minutes du lien tient pour ce parcours-là aussi. Il a été choisi pour la réinitialisation de mot de passe, en tenant compte de la remise et du temps de relever sa boîte ; rien ne dit qu'il ait été pesé pour quelqu'un qui cherche d'abord son téléphone

### Le recours en console, qui doit exister quoi qu'il arrive
- [ ] `docker compose exec authelia authelia storage user totp delete <login>` fonctionne **en 4.39.22**, et la commande exacte est recopiée ici telle qu'elle a répondu. La forme de cette CLI a changé entre versions ; celle qui est écrite dans `AUTH-7` date d'avant la montée et n'a jamais été exécutée sur cette instance
- [ ] Après suppression, le compte se ré-enrôle de bout en bout à la connexion suivante. Sans cette vérification, on n'a pas un recours mais une commande qui rend `OK`
- [ ] `webauthn delete` est cité à côté dans `AUTH-7`. Est-il seulement pertinent ici — WebAuthn est-il activé sur cette instance ? Si non, le recours est plus simple qu'écrit, et l'écrire faux coûtera une minute de doute le jour où il servira

### Remettre en état
- [ ] `stagiaire` est retiré de `bd-admins`, et son TOTP éventuel est supprimé. Une passe qui laisse un compte d'essai administrateur a fabriqué le problème qu'elle mesurait
- [ ] Les comptes d'administration réels sont vérifiés intacts : chacun se connecte encore avec son appareil. La passe n'a touché qu'`stagiaire`, et le vérifier coûte deux connexions

## Où reportent les constats

Un chemin de secours ABSENT ne rouvre pas cette passe : il devient une case d'`AUTH-7`,
dans la zone « ce qu'il faut savoir avant de choisir », parce qu'il pèse sur le choix du
panneau — `asalimonov/authelia-admin` annonce la gestion des appareils TOTP, et c'est
exactement ce que ce trou rendrait précieux. Il pèse aussi sur `AUTH-6`, qui porte le
modèle de comptes : « un seul administrateur » cesse d'être tenable si le recours est en
console et que la console est derrière le compte bloqué.

Un chemin de secours PRÉSENT ferme le sujet et corrige `AUTH-7`, dont la phrase « console
uniquement » serait alors trop large — elle vaut pour réinitialiser QUELQU'UN D'AUTRE, pas
pour se dépanner soi-même, et la nuance change la conclusion.

Dans les deux cas, la contradiction relevée en tête se lève dans `INFRA-8` : sa phrase
« appareil perdu compris » doit dire lequel des deux cas elle a éprouvé.
