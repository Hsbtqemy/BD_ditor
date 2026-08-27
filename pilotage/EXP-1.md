---
chantier: EXP-1
statut: différé
---

# EXP-1 — exposer les exports de dépôt dans l'UI

**Point de départ** — mis en attente exprès derrière INFRA-1 : tant que l'outil tourne en
mono-poste, le chercheur est **sur** la machine de la base et lance les scripts `tools/`
au shell. Déployé, cet accès disparaît.

## Reste

- [ ] Un bouton produit la fiche de description de collection et les enregistrements de métadonnées côté serveur, sans accès shell
- [ ] Le manifeste IIIF est produit par la même voie
- [ ] Le fichier produit est téléchargeable par le navigateur ET déposable sur ShareDocs, sur le patron déjà en place pour `/api/sauvegarde`
- [ ] Les cœurs restent partagés entre la CLI et la route : aucune logique d'export n'est réécrite côté serveur, comme l'import de vocabulaire a déjà une CLI et un bouton
- [ ] Le choix d'exposer ou non le crosswalk et la provenance est tranché et écrit

## Contexte

**Différé, pas interrompu.** Mise en attente actée le 2026-08-27. Aucun code n'a été
écrit ; c'est le C5 de `docs/roadmap.md`, renommé ici en EXP-1 pour suivre le vocabulaire
de codes du journal.

Le raisonnement tient en une phrase : la doctrine « scripts hors-app » supposait le
mono-poste. Elle ne survit pas au déploiement — non parce qu'elle était mauvaise, mais
parce que sa condition disparaît.

Le patron existe déjà deux fois dans le dépôt (`/api/sauvegarde` pour le fichier produit
côté serveur, `lexique_import.py` pour le cœur partagé CLI + route). Ce chantier n'invente
rien : il applique. C'est ce qui le rend peu risqué une fois INFRA-1 fait.
