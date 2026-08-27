---
chantier: UX-3
statut: à venir
---

# UX-3 — hiérarchie et découvrabilité des actions

**Point de départ** — UX-1 (nav transverse) et UX-2 (en-tête en deux bandes) sont livrés ;
la hiérarchie **à l'intérieur** d'une surface n'a jamais été reprise.

## Reste

- [ ] Les quatre modes de la Visionneuse (Navigation, Édition, Annotation, Transcription) sont distinguables sans lire la documentation : ce que chaque mode permet est visible avant de cliquer
- [ ] Dans chaque mode, l'action principale se distingue visuellement des actions secondaires
- [ ] Le panneau Grammaire indique ce qu'il attend quand aucun token n'est sélectionné, plutôt que de rester vide
- [ ] Une personne qui n'a jamais utilisé l'outil trouve « annoter une bulle » et « corriger une transcription » sans aide, et le fait est constaté sur quelqu'un de réel, pas supposé

## Contexte

Effort M, priorité P3. La dernière case est délibérément la plus dure : c'est la seule
qui distingue « on a réorganisé des boutons » de « la découvrabilité a augmenté », et
elle ne se coche pas depuis une machine.

À traiter avec UX-4 : les deux touchent les mêmes fichiers (`static/viewer.js`,
`static/style.css`) et les séparer ferait deux passes de régression visuelle au lieu
d'une.
