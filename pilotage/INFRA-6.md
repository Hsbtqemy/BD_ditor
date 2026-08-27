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

Cette contrainte pousse la fiche derrière INFRA-3 (identifiants persistants chiffrés),
elle-même derrière INFRA-1. À ne pas commencer en croyant que c'est un petit sujet de
tuyauterie.
