---
chantier: ARCH-1
statut: à venir
---

# ARCH-1 — décider du sort de main.py avant qu'il ne soit illisible

**Point de départ** — `main.py` porte toutes les routes de l'application : 2 897 lignes au
2026-08-27. Aucune décision n'a été prise, et aucune n'est urgente — c'est ce que cette
fiche existe pour garder vrai.

## Reste

### Arbitrage
- [ ] Le seuil est franchi ou approché, et le choix est tranché et écrit : découper par domaine (albums, planches, régions, analyse, export), extraire vers des routeurs FastAPI, ou assumer le fichier unique et dire pourquoi
- [ ] Si le découpage est retenu, il ne casse ni les chemins de routes ni le contrat d'API : les tests passent sans être réécrits

### Si l'on assume
- [ ] La raison d'assumer est écrite dans `docs/`, pour que la question ne se repose pas tous les six mois

## Contexte

Cette fiche est la **cible de la veille à seuil** déclarée dans
`pilotage/journal.config.mjs` : `main.py`, seuil 3 200 lignes. Sans elle, le chiffre
monterait sur le tableau de bord sans que personne sache où la décision se prend.

Elle ne vient pas du backlog ni de l'audit — c'est un ajout de la mise en place du
journal, et le seul de la série. À supprimer sans état d'âme si le fichier unique est un
choix assumé : dans ce cas, cocher la dernière case et clore.

Le dépôt n'a **aucune étape de build** et c'est un principe, pas un manque : on ouvre les
fichiers et on les lit. Un fichier de 3 000 lignes est en tension directe avec ce
principe — c'est ce qui rend le seuil réel plutôt qu'esthétique. Le second candidat est
`static/viewer.js` (2 500 lignes), non surveillé pour l'instant : un seul chiffre à
limite réelle, sinon la veille devient un tableau de bord de plus.
