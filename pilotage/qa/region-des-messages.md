---
passe: La région des messages, entendue au lecteur d'écran
chantier: ANN-8
duree: 10 min
derniere: 2026-10-23
---

# QA — le premier message d'une page est annoncé par un lecteur d'écran

**Écrite le 2026-10-23.** Elle mesure ce qu'aucun test ne mesure : `ANN-8`, case « La région des
messages existe avant son premier message, sur les cinq surfaces ». Depuis `d87bbdc`,
`static/theme.js` pose la région des messages (`#toasts`, vide, annoncée poliment) au chargement
de chaque page, et un test vérifie qu'elle naît AVANT son premier message. Une région qui naît
AVEC son message n'est souvent pas annoncée : c'est ce qu'on écoute ici, sur le PREMIER message
d'une page tout juste chargée.

**Ce que la passe ne juge pas** : la Recherche et l'Administration n'émettent aucun message de
cette sorte — leur région existe, rien ne la remplit ; elles ne se mesurent donc pas ici. Les
messages d'une ligne d'état propre à un bloc (« Déplacée : … » de la Bibliothèque) ne passent pas
par cette région.

Narrateur de Windows : **Ctrl + Windows + Entrée** l'allume et l'éteint. Chaque case commence par
un rechargement (F5) : c'est le PREMIER message de la page qu'on écoute. La recette, telle
qu'elle est ; les fenêtres privées de la passe en cours.

## Reste

### Trois surfaces, un premier message chacune — Narrateur allumé

- [x] Sous `lectrice`, Atelier, F5, attendre que la planche s'affiche, puis Ctrl+Z : la bulle « Rien à annuler. » apparaît, et Narrateur la LIT, sans qu'on ait déplacé le focus
- [ ] Sous `proprio`, Bibliothèque, fiche de « Lot TIFF QA », F5, « Modifier », *Enregistrer* sans rien changer : la bulle « Album enregistré » apparaît, et Narrateur la lit
- [ ] Sous `proprio`, Exploration, F5, « 📖 Lexique », déplier un tag, changer un mot de sa définition puis Tab (le champ s'enregistre en perdant le focus) : la bulle « Enregistré » apparaît, et Narrateur la lit
- [x] Narrateur éteint (Ctrl + Windows + Entrée) à la fin
