---
chantier: INFRA-6
statut: à venir
---

# INFRA-6 — sauvegardes automatiques vers ShareDocs

**Point de départ** — le dépôt **manuel** d'une sauvegarde sur ShareDocs existe et
fonctionne (`pipeline/backup.py` + `pipeline/sharedocs.py`) ; rien ne le déclenche tout
seul.

## Reste

- [ ] Une sauvegarde est déposée périodiquement sur ShareDocs sans intervention
- [ ] Une rotation supprime les anciennes sauvegardes selon une règle écrite, et ne peut pas supprimer la dernière réussie
- [ ] Un échec de dépôt (réseau, identifiants expirés) est visible sans consulter les logs, et ne laisse pas de sauvegarde partielle sur le serveur distant
- [ ] La périodicité est désactivable, et l'est par défaut en mono-utilisateur local

## Contexte

Effort M, priorité P3. La partie difficile n'est pas le dépôt — il est déjà écrit et
testé sous MockTransport — mais le **déclencheur** : l'application n'a pas
d'ordonnanceur, et les identifiants ShareDocs ne vivent qu'en mémoire serveur (doctrine
CLAUDE.md). Un dépôt automatique après redémarrage n'aurait donc aucun identifiant à
utiliser tant qu'un humain ne les a pas re-saisis.

Cette contrainte pousse la fiche derrière INFRA-3 (identifiants persistants chiffrés).
**INFRA-3 n'attend plus rien depuis le 2026-09-05** — son propre verrou, INFRA-1, est levé,
et cette page le décrivait encore comme bloqué. La chaîne n'a donc plus qu'un maillon :
INFRA-3 tranche s'il faut persister des secrets chiffrés, ce qui est une rupture de
doctrine assumée et non un portage, et INFRA-6 suit. À ne pas commencer en croyant que
c'est un petit sujet de tuyauterie.

**INFRA-3 a tranché le 2026-09-10 (`4221748`, livré), et le blocage a changé de nature**
— relu le 2026-09-11. La réponse est NON, on ne persiste pas, et la question s'est dissoute :
le compte d'INSTANCE se recharge seul de l'environnement (`BD_SHAREDOCS_URL` / `_USER` /
`_PASS`) au premier accès, donc un redémarrage ne le perd pas. C'est lui qu'un dépôt
automatique emploierait, et le paragraphe précédent, qui ne voyait que des identifiants
saisis à la main, est dépassé. Mais l'équipe a décidé le même jour de laisser ces trois
variables VIDES sur la production, la racine utile dépendant du projet. Un dépôt
automatique n'a donc aujourd'hui AUCUN compte à employer. Ce chantier attend que ces
variables soient posées — une décision d'équipe, pas un chantier de code —, puis le choix
d'un déclencheur, l'application n'ayant toujours pas d'ordonnanceur.
