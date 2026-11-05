# Les illustrations de l'album de présentation (UX-6)

Des images FIXES, que l'album « Bienvenue dans BéDéditeur » (`static/wizard.js`,
`illustration(page)`) pose sur ses pages 2 à 5. Décidé par Hugo le 2026-11-05 : ce sont des
illustrations d'un outil, pas des données ; elles ne lisent rien de l'instance. Les zones, les
lectures d'OCR et le vocabulaire qu'on y dessine sont écrits dans `static/lib/wizard.js`
(`ILLUSTRATIONS`) et INVENTÉS pour l'exemple.

Chaque fichier est un recadrage réduit d'une planche, à environ deux fois sa taille
d'affichage. Les sources ne sont pas dans le dépôt : ce sont les planches du jeu des bacs à
sable (`tools/preparer_jeu.py`).

**Ces images ne servent qu'à l'album de présentation.** Deux fondements, selon la source :

- **part dépôt du jeu, exportable** — une planche que Hugo a déclarée exportable, donc libre ;
- **citation et illustration, cadre scientifique non commercial** — décision de Hugo du
  2026-11-05, limitée à l'album de présentation : aucun autre écran, aucun autre usage.

| Fichier | Source (titre, page) | Recadrage, en pixels du scan | Fondement |
|---|---|---|---|
| `corpus-lightning-31.jpg` | *Lightning Comics* n° 6, page 31 (`lightning-31.jpg`) | le haut de la planche, 3:4, réduit à 120 × 160 | part dépôt du jeu, exportable |
| `corpus-lightning-35.jpg` | *Lightning Comics* n° 6, page 35 (`lightning-35.jpg`) | le haut de la planche, 3:4, réduit à 120 × 160 | part dépôt du jeu, exportable |
| `corpus-modern-76.jpg` | *Modern Comics* n° 76, page 1 (`modern-76-p1.jpg`) | le haut de la planche, 3:4, réduit à 120 × 160 | part dépôt du jeu, exportable |
| `corpus-saint-cyr.jpg` | Girin, *L'École de Saint-Cyr* (`girin-saint-cyr.jpg`) | le haut de la planche, 3:4, réduit à 120 × 160 | part dépôt du jeu, exportable |
| `corpus-moustache.jpg` | Calvo, *Moustache et Trottinette*, « Le brigand de la Mare-Moussue », planche 3 (`calvo-moustache.jpg`) | le haut de la planche, 3:4, réduit à 120 × 160 | citation et illustration, cadre scientifique non commercial (Hugo, 2026-11-05), limitée à l'album de présentation |
| `zones-moustache-case.jpg` | Calvo, *Moustache et Trottinette*, planche 3 : la case 1 de la dernière rangée (`calvo-moustache.jpg`) | x 8, y 964, 305 × 324 (scan 975 × 1296), taille d'origine | citation et illustration, cadre scientifique non commercial (Hugo, 2026-11-05), limitée à l'album de présentation |
| `moteurs-moustache-rangee.jpg` | Calvo, *Moustache et Trottinette*, planche 3 : la dernière rangée (`calvo-moustache.jpg`) | x 0, y 962, 975 × 328, réduit à 660 × 222 | citation et illustration, cadre scientifique non commercial (Hugo, 2026-11-05), limitée à l'album de présentation |

*Bibi Fricotin chez les Chinois*, de la part dépôt, n'est pas employé : ses caricatures n'ont
pas leur place dans une page d'accueil. *Radar* reste hors du dépôt.
