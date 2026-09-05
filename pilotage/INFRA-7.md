---
chantier: INFRA-7
statut: à venir
---

# INFRA-7 — la session est trop courte pour du travail d'annotation

**Point de départ** — 2026-09-05, à l'annonce de comptes stagiaires. Rien n'est écrit ;
le constat vient de la configuration livrée par INFRA-1, relue et non éprouvée.

## Reste

### Mesurer avant de changer
- [ ] Ce que `inactivity: 15 minutes` fait sur une session ORDINAIRE : connexion, quinze minutes sans toucher l'onglet, retour — le portail redemande mot de passe ET code TOTP
- [ ] Ce que la case « se souvenir de moi » change vraiment : la même attente, case cochée à la connexion. La session survit-elle à l'inactivité, ou seulement jusqu'à `expiration` ? La documentation ne suffit pas à trancher, et se tromper ici fait choisir les trois valeurs à l'aveugle
- [ ] Ce qu'une expiration fait à un LOT ML en cours : un lot lancé depuis la Bibliothèque tourne dans un thread serveur, donc l'expiration ne devrait pas l'interrompre — mais l'écran qui suit sa progression interroge l'API, et un 401 en pleine barre de progression ne ressemble pas à une déconnexion

### Décider
- [ ] Les trois valeurs sont tranchées sur un attendu ÉCRIT (« une journée de travail sans ressaisir »), et non sur une intuition de confort
- [ ] La 2FA reste exigée, ou bien la dérogation choisie est nommée : par GROUPE (`subject: ['group:annotateurs']`) ou par RÉSEAU (`networks:`), jamais « on verra »
- [ ] Le choix est écrit dans `docs/deploiement-docker.md` avec sa raison — la ligne `# mets 'one_factor' si tu ne veux PAS imposer la 2FA` invite à l'assouplissement sans dire ce qu'on perd

## Contexte

Trois lignes gouvernent le confort réel, et ce n'est PAS la politique 2FA :

```yaml
expiration: '1 hour'
inactivity: '15 minutes'
remember_me: '1 month'
```

La 2FA est demandée une fois par session. C'est `inactivity` qui mord tous les jours —
l'annotation passe beaucoup de temps à regarder autre chose que l'écran : l'album papier,
un dictionnaire, une note. Quinze minutes est un réglage de banque, pas d'atelier.

**Le danger est d'assouplir du mauvais côté.** Passer en `one_factor` répond à l'agacement
en affaiblissant les comptes les plus nombreux et les moins surveillés ; allonger la
session répond au même agacement sans rien céder. Le second devrait être essayé d'abord —
et si la 2FA doit tomber, que ce soit une décision datée avec son motif, pas la ligne de
moindre résistance offerte par un commentaire du gabarit.

Les ordinateurs multiples ne sont PAS le problème : le secret TOTP appartient au compte et
non à la machine. Un stagiaire enrôle son téléphone une fois et se connecte de partout.
