---
chantier: UX-3
statut: interrompu
---

# UX-3 — hiérarchie et découvrabilité des actions

**Arrêté sur** — 2026-10-16, `8ca053e` : ↗ « Ouvrir dans l'Atelier » a la boîte de ses voisins,
sur la ligne d'une planche de la Bibliothèque (relevé par Hugo pendant une passe de COL-3). C'est
le SEUL commit de code du chantier, et il ne touche aucune des quatre cases d'origine. Le statut
passe d'`à venir` à `interrompu` le 2026-10-21 pour cette raison seule — l'outil dément un
`à venir` qui porte un commit de code —, comme UX-12 avant lui : la hiérarchie à l'intérieur des
surfaces n'est toujours pas reprise.

**Point de départ** — UX-1 (nav transverse) et UX-2 (en-tête en deux bandes) sont livrés ;
la hiérarchie **à l'intérieur** d'une surface n'a jamais été reprise.

## Reste

- [ ] Les quatre modes de la Visionneuse (Navigation, Édition, Annotation, Transcription) sont distinguables sans lire la documentation : ce que chaque mode permet est visible avant de cliquer
- [ ] Dans chaque mode, l'action principale se distingue visuellement des actions secondaires
- [ ] Le panneau Grammaire indique ce qu'il attend quand aucun token n'est sélectionné, plutôt que de rester vide
- [ ] Une personne qui n'a jamais utilisé l'outil trouve « annoter une bulle » et « corriger une transcription » sans aide, et le fait est constaté sur quelqu'un de réel, pas supposé
- [x] Bibliothèque, ligne d'une planche : ↗ « Ouvrir dans l'Atelier » a la boîte de ses voisins — attendu : 26 × 26 px comme 🏷 et 🔓, à la même hauteur, sans soulignement. C'était un lien en ligne, qui ignorait largeur et hauteur : un glyphe souligné de 12 × 19 px (relevé par Hugo le 2026-10-16, sur la recette). **Fait par `8ca053e`**, mesuré dans les deux thèmes

## Contexte

Effort M, priorité P3. La dernière case est délibérément la plus dure : c'est la seule
qui distingue « on a réorganisé des boutons » de « la découvrabilité a augmenté », et
elle ne se coche pas depuis une machine.

À traiter avec UX-4 : les deux touchent les mêmes fichiers (`static/viewer.js`,
`static/style.css`) et les séparer ferait deux passes de régression visuelle au lieu
d'une.
