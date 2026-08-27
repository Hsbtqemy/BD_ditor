---
chantier: INFRA-3
statut: différé
---

# INFRA-3 — credentials WebDAV par utilisateur

**Point de départ** — mis en attente exprès : sans sessions réelles (INFRA-1), il n'y a
pas d'utilisateur à qui rattacher des identifiants.

## Reste

- [ ] Chaque utilisateur enregistre ses propres identifiants ShareDocs, et le compte maître Huma-Num n'est jamais saisi dans l'application
- [ ] Les identifiants sont stockés chiffrés, jamais en clair sur disque
- [ ] Un dépôt ShareDocs effectué par un utilisateur porte bien son identité côté serveur distant
- [ ] Le comportement mono-utilisateur local reste inchangé quand aucune auth n'est configurée

## Contexte

**Différé, pas interrompu** : c'est une mise en attente délibérée derrière INFRA-1, pas
un travail abandonné en cours de route. Mise en attente actée le 2026-08-27 ; aucun
commit de code n'a jamais cité ce code.

**Ce n'est pas du confort, c'est une fuite qui s'ouvre au 2ᵉ utilisateur.** Vérifié le
2026-08-27 : `pipeline/sharedocs.py:34` garde `_session = {"url", "user", "password"}` en
**variable globale de module**, et `configure()` (`:186`) l'écrase pour tout le process.
Déployé en multi-utilisateur, la personne qui configure ShareDocs le configure pour tout
le monde, et le dépôt lancé par quelqu'un d'autre partira **avec ses identifiants à
elle**. À traiter avant d'ouvrir l'accès à un second compte, pas après.

Rupture de doctrine à noter : aujourd'hui ces identifiants vivent **en mémoire serveur
uniquement, jamais sur disque** (cf. CLAUDE.md). Cette fiche introduit délibérément un
stockage persistant — donc un secret à chiffrer, une clé à gérer, et une décision de
conception qui n'est pas encore prise. Ce n'est pas un simple portage de l'existant.

Dépend d'AUTH-1 : sans utilisateur en base, il n'y a personne à qui rattacher un secret.
