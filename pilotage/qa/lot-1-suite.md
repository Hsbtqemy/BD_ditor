---
passe: Le push qui suit le lot 1 — l'ordre des planches, ce qu'un type retire, les tags, le zoom
chantier: —
duree: 70 min
derniere: —
---

# QA — après le lot 1 : le nom et l'ordre des planches, le miroir du type, « Passer ce geste », supprimer / fusionner / renommer un tag, le zoom d'interface

**Écrite le 2026-10-22 sur la recette reconstruite sur `69b3515`**, décor de l'état `apres-lot1`
(la fin de la passe du lot 1, schéma 34 : « Lot TIFF QA » — trois planches, page-1.tif,
page-2.tif, page-10.tif — dans « Collection Test » ; « Lot JP2 QA » dans « Étude B » ; « esther
v1 » converti ; tous les tags sont GLOBAUX ; dans « Lot TIFF QA », « pl.3 », une case porte la
situation « lieu : falaise » et une boîte personnage montre « Zed QA »). Non jouée. Elle porte sur
`UX-11` (`7499e53`, `228d72e`, `5482db3`, `f3ed04a` : le nom du fichier d'origine, un refus en
mots, « Ranger par nom de fichier », ↑ ↓), `ANN-8` (`0f09de5` … `4e8610b` : une région perd ce
que son nouveau type ne montre pas et Ctrl+Z le rend, « Passer ce geste », l'accent, l'infobulle
de « Citation » ; `2f03f63` … `a77a93f` : renommer, fusionner, supprimer un tag, Ctrl+Z qui ne
recrée pas un tag, le tag local tenu dans sa collection) et `UX-7` (`fc0f952`, `6e3320b` : sous
le zoom d'interface, tiroirs, menu « Aa », modales et cadres de page tiennent dans la fenêtre).

**Ce que les tests couvrent déjà — ne pas le refaire ici** : l'ordre naturel des noms et les
phrases de confirmation (tables Node), le 409 de l'ordre sous deux identités, l'ordre hors
Ctrl+Z et hors « travail d'autrui », `aria-disabled` et l'audit axe des flèches éteintes, le 507
réservé au disque ; la photographie des liens au changement de type, la garde de portée et de
dimension de leur retour, la trace « passer » et ses revérifications ; la comparaison sans
accents des deux côtés ; les droits de chaque geste sur un tag sous chaque portée, la chaîne
`tags` du journal, l'index plein texte refait ; les mesures du zoom à 320, 375 et 768 px sous
1,4 et 2, dans Chromium et Firefox.
**Ce qui se regarde ici** : ce que l'écran DIT à chaque geste, et si l'on s'y retrouve.

**Ce que la passe ne juge pas** : `BD_NLP_PREWARM` (un réglage de déploiement, sans écran) ; le
filet serveur des homonymes (une liste lue trop tôt) ; les deux outils de maintenance à blanc,
`tools/retirer_liens_caches.py` et `tools/tags_hors_collection.py` (au déploiement, sur le mot
de Hugo) ; l'outil de conversion, qui dit désormais sa progression (`69b3515`) — il n'a plus
rien à convertir sur la recette ; la phrase « — n tag(s) non rendu(s) » d'une annulation qui
rend autre chose ET bute sur un tag supprimé (`a77a93f`), qu'un geste d'écran ne compose pas — un
retrait de tag est un acte à lui seul, et celui qui ne porte que sur un tag disparu est passé ;
la fenêtre plus basse que le chrome, au-delà de 160 % à
320 × 640 (relevée, non traitée : `UX-7`).

Les zones se jouent DANS L'ORDRE. Une fenêtre privée par compte, gardée jusqu'au bout. La
dernière zone rend la recette.

## Reste

### Le décor — PowerShell, puis comptes `admin-bd` et `proprio`

- [x] `C:\temp\bd-recette\etat-de-base.ps1 restaurer apres-lot1` finit par « bd-app : running » ; sous `admin-bd`, `https://bd.127-0-0-1.sslip.io/administration?vue=instance` : « 🏷️ Version servie » affiche `69b3515` ou plus récent
- [x] Le dossier de travail, HORS du dépôt : `$t = 'C:\temp\qa-suivant'; New-Item -ItemType Directory -Force $t | Out-Null; Copy-Item 'C:\temp\scans-essai\esther-vol1_006.tif' "$t\page-20.tif"; Set-Content -Encoding ascii "$t\page-21.tif" "pas une image"` — puis `(Get-ChildItem $t -File).Count` répond `2`

### Quel fichier est devenu quelle planche — compte `proprio`, Bibliothèque, « Lot TIFF QA »

- [x] Fiche de « Lot TIFF QA » : survoler la ligne de « planche 3 » → l'infobulle dit « Fichier : page-10.tif » ; la ligne de « planche 1 », « Fichier : page-1.tif » — le nom seul, aucun dossier
- [x] « ⤓ Importer des planches… », dans `C:\temp\qa-suivant` les deux fichiers, *Ouvrir* : le bilan dit « page-20.tif → planche 4 », et, sous les refus, « **page-21.tif** n'est pas une image lisible : son format n'est pas reconnu, ou le fichier est abîmé. » — le nom en gras, une seule fois, aucun « BytesIO »
- [x] Fiche d'« esther v1 » : survoler la ligne de sa première planche → « Fichier : planche_0001.tif » (le nom que l'outil de conversion a noté sur la recette pendant la passe du lot 1)

### Changer l'ordre des planches — comptes `proprio` puis `lectrice`, Bibliothèque, « Lot TIFF QA »

- [x] Sous `proprio`, fiche de « Lot TIFF QA » : chaque ligne de planche porte ↑ ↓ avant ses autres gestes ; le ↑ de la première ligne et le ↓ de la dernière sont éteints ; au-dessus du tableau, « ⇅ Ranger par nom de fichier »
- [x] « ⇅ Ranger par nom de fichier » : une ligne sous les boutons dit « Les planches sont déjà dans l'ordre des noms de fichier. », sans rien demander — page-1, page-2, page-10, page-20 : 2 avant 10
- [x] ↓ de « planche 1 » : la ligne dit « Déplacée : c'est maintenant la planche 2 (i.002). » ; survolée, la ligne « planche 2 » dit « Fichier : page-1.tif » ; le focus est resté sur le ↓ de cette planche — Entrée la descend encore (« … la planche 3 (i.003). »)
- [x] « ⇅ Ranger par nom de fichier » : la confirmation dit « Ranger les planches dans l'ordre des noms de fichier ? » puis « 3 planches changent de place. Les numéros éditoriaux et les citations « pl·c·b » qui en dérivent changent : une citation faite avec l'ancien numéro ne désignera plus la même planche. » ; *Annuler* ne change rien ; *OK* : « Planches rangées dans l'ordre des noms de fichier : 3 planches ont changé de place. », et page-1.tif est revenu en « planche 1 »
- [x] *Relecture* → « à faire » : les flèches restent visibles, en pointillés ; en toucher une écrit « Retirez le filtre de relecture pour changer l'ordre : il cache des planches, et un cran se compte dans l'album entier. » et rien ne bouge ; *Relecture* → « toutes » : elles reviennent pleines
- [x] Deux onglets de `proprio` sur la fiche de « Lot TIFF QA » : ↓ de « planche 1 » dans le premier ; dans le second, SANS recharger, ↓ de « planche 3 » : « Conflit : l'ordre des planches a été changé depuis un autre écran de ce même compte, le … (UTC) depuis que vous l'avez vu. Votre modification n'est pas enregistrée. », et la fiche du second montre l'ordre du premier ; puis « ⇅ Ranger par nom de fichier », *OK*, pour revenir à page-1, page-2, page-10, page-20
- [x] Atelier, « Lot TIFF QA », Ctrl+Z : il ne touche pas à l'ordre des planches — il dit qu'il n'y a rien à annuler, ou défait un geste d'annotation
- [x] Sous `lectrice`, fiche de « Lot TIFF QA » : aucune flèche, aucun « ⇅ Ranger par nom de fichier »

### Ce qu'un type retire, et Ctrl+Z qui le rend — compte `proprio`, Atelier, « Lot TIFF QA », « pl.3 »

- [x] La boîte personnage qui montre « Zed QA » (mode Édition, `E`) → *Type* « bulle » : une bulle dit « Personnage montré « Zed QA » retiré : ce type de région ne le montre pas. Ctrl+Z le rend. »
- [x] Ctrl+Z : la région redevient boîte personnage ET montre de nouveau « Zed QA » — un seul geste
- [x] La case qui porte la situation « lieu : falaise » → *Type* « bulle » : « Situation retirée (1 valeur) : ce type de région ne la montre pas. Ctrl+Z la rend. » ; Ctrl+Z : c'est une case, et sa situation dit de nouveau « lieu : falaise »
- [x] Une bulle qui a un locuteur → *Type* « case » : « Locuteur « … » retiré : ce type de région ne le montre pas. Ctrl+Z le rend. » ; Ctrl+Z le rend

### Deux noms, un personnage — compte `proprio`, Atelier, « Lot TIFF QA », « pl.3 », mode Annotation

- [x] Première bulle : champ du locuteur, taper « Élodie QA », Entrée → le locuteur devient « Élodie QA » (un personnage neuf)
- [x] Seconde bulle : taper « elodie qa » → la liste propose « Élodie QA » ; Entrée : c'est « Élodie QA » qui est posé ; la liste du registre ne montre aucun « elodie qa »

### « Passer ce geste » — comptes `proprio` et `stagiaire` (qui écrit dans « Collection Test »), Atelier, « Lot TIFF QA », « pl.2 » — REJOUÉE sur la recette reconstruite (le premier essai a trouvé un défaut de Ctrl+Z, corrigé)

- [ ] Sous `proprio`, la bulle de « pl.2 », mode Annotation : poser le locuteur « Zed QA »
- [ ] Sous `stagiaire`, même album, même bulle (F5) : remplacer le locuteur par « Yann QA »
- [ ] Sous `proprio`, F5, Ctrl+Z : une bulle rouge dit « Annulation impossible : le locuteur a été modifié depuis par … » (le nom de `stagiaire`, et l'heure) suivie d'un bouton « Passer ce geste », dont l'infobulle dit « Ctrl+Z remontera au geste d'avant ; le travail de l'autre reste. » ; la bulle porte toujours « Yann QA » ; Ctrl+Z une seconde fois redonne le même refus
- [ ] « Passer ce geste » : « Geste passé : … . Ctrl+Z remonte au geste d'avant. » ; la bulle a toujours « Yann QA » ; Ctrl+Z suivant : il ne parle plus de ce locuteur — il défait un geste plus ancien de `proprio`, ou dit qu'il n'y a rien à annuler
- [ ] Refaire un refus (poser, changer sous `stagiaire`, Ctrl+Z sous `proprio`) et ne pas toucher le bouton : la bulle disparaît d'elle-même au bout d'une quinzaine de secondes

### L'infobulle de « Citation » — compte `proprio`, Atelier

- [x] Une bulle sélectionnée, survoler la ligne « Citation » du panneau : « Citation tirée de l'ordre de lecture : elle change si une case est ajoutée ou déplacée. Pour désigner une bulle, écrivez son identifiant (#…, ligne « Région »). »

### Renommer, supprimer un tag, et ce que Ctrl+Z en fait — compte `proprio`, Atelier puis Exploration → « 📖 Lexique »

- [x] Exploration, « 📖 Lexique », déplier le tag « variation » (global, posé) : AUCUN bouton « Renommer », « Fusionner », « Supprimer » — un tag global posé ne se remanie que par un administrateur
- [x] Déplier « qa-conflit » (global, posé nulle part) : « Renommer » et « Supprimer », pas de « Fusionner » ; le champ à côté de « Renommer » → « qa-conflit-2 », *Renommer* : « Tag « qa-conflit » renommé « qa-conflit-2 ». »
- [x] Atelier, « Lot TIFF QA », « pl.3 », une bulle : ajouter le tag « qa-ephemere », puis le retirer ; Exploration, « 📖 Lexique », « qa-ephemere » → *Supprimer* : « Supprimer le tag « qa-ephemere » ? Aucune région ne le porte. », *OK* : « Tag « qa-ephemere » supprimé. »
- [x] Retour à l'Atelier, F5, Ctrl+Z : « Ne s'annule plus : … — l'état d'avant ne peut plus être rétabli. » — le retrait ne portait que sur un tag qui n'existe plus ; la bulle ne porte pas « qa-ephemere », et le Lexique, rouvert, ne le montre pas : Ctrl+Z ne recrée jamais un tag
- [x] La même bulle : ajouter « qa-avant », le retirer ; Lexique, « qa-avant » → renommer en « qa-apres » ; Atelier, F5, Ctrl+Z : « Annulé : … », la bulle porte « qa-apres », et le Lexique n'a aucun « qa-avant » — Ctrl+Z a suivi le renommage

### Un tag local, et ce qu'un administrateur remanie — comptes `proprio` puis `admin-bd`

- [x] Sous `proprio`, Lexique, « qa-onglet-2 » → *Portée* « Étude B » (que `proprio` possède) ; Atelier, « Lot JP2 QA » (rangé dans « Étude B »), une région, « Ajouter un tag… » : taper « qa-on » → « qa-onglet-2 » est proposé ; Entrée le pose
- [x] Atelier, « Lot TIFF QA » (rangé dans « Collection Test »), une bulle : « qa-on » ne propose PAS « qa-onglet-2 » ; le taper en entier, Entrée : « Le tag « qa-onglet-2 » est propre à la collection « Étude B » : il ne se pose que sur les albums qu'elle range. », et la bulle ne le porte pas
- [x] Lexique, « qa-onglet-2 » (local à « Étude B », posé) : « Renommer », « Fusionner », « Supprimer » sont offerts à `proprio`, propriétaire de sa collection ; le menu « Fusionner dans… » ne propose que des tags globaux ou de « Étude B »
- [x] Sous `admin-bd`, Lexique, « exemple cours » (posé sur 2 régions) → *Fusionner dans…* « variation », *Fusionner* : la confirmation dit « Fusionner « exemple cours » dans « variation » ? 2 régions passeront à « variation » » (avec « (… le portent déjà) » si c'est le cas) « , et « exemple cours » disparaîtra. » ; *OK* : « « exemple cours » fusionné dans « variation » (2 régions). », et « exemple cours » a quitté le Lexique
- [x] Sous `admin-bd`, « grille-b » (posé sur 1 région) → *Supprimer* : « Supprimer le tag « grille-b » ? Il sera retiré de 1 région. » ; *OK* : « Tag « grille-b » supprimé et retiré de 1 région. »

### Le zoom d'interface, borné par la largeur — compte `proprio`, outils de développement en mode appareil (largeur réglable), réécrite le 2026-10-23 après la décision de Hugo

- [ ] 320 px, Atelier, menu « Aa » → « A+ » : rien ne grossit ; « A+ » est éteint (contour pointillé), et son infobulle dit « Zoom maximal pour cette largeur de fenêtre. Le zoom du navigateur, lui, réagence la page. » ; aucune barre de défilement de côté
- [ ] 448 px, Atelier, « A+ » jusqu'à ce qu'il s'éteigne (environ 140 %) : ☰ — le tiroir des planches laisse à sa droite une bande de voile, un clic dessus le ferme ; le tiroir de structure laisse une bande à sa gauche, un clic la ferme
- [ ] Toujours à 448 px au plus grand, menu « Aa » : son panneau reste dans la fenêtre, « A− » et « ↺ » s'atteignent
- [ ] *Passe du lot 1, rejouée à la largeur où le zoom reste permis* — 448 px, au plus grand, ☰ : les deux libellés et les deux listes restent lisibles et ne débordent pas du tiroir, et la liste des planches s'atteint en faisant défiler le tiroir
- [ ] *Passe du lot 1, rejouée de même* — 448 px, au plus grand, « Lot TIFF QA », « pl.3 », mode Annotation, une bulle sélectionnée : « Attribuer un personnage… » et « Ajouter un tag… » tiennent dans la largeur du tiroir — aucun ne déborde, le tiroir ne défile pas de côté ; même chose sur la case de la situation pour « dimension : valeur… »
- [ ] 1280 px : Bibliothèque, « A+ » jusqu'à 200 % (il s'éteint là) ; puis Atelier : le zoom y est plus petit — « A+ » éteint vers 150 %, la bande d'outils tient sur sa ligne, rien ne sort à droite ; puis 375 px : le zoom tombe vers 117 % ; retour à 1280 px : la Bibliothèque est de nouveau à 200 % — la préférence n'a pas été perdue
- [ ] 640 px, Bibliothèque au plus grand (200 %), fiche de « Lot TIFF QA », « Modifier » : la boîte tient dans la fenêtre, voile visible des deux côtés, titre et dernier bouton atteints en faisant défiler la BOÎTE, Échap la ferme ; même chose pour Exploration → « 📖 Lexique » ; puis « ↺ » : tout revient à 100 %

### Rendre la recette — PowerShell

- [ ] `Remove-Item -Recurse -Force C:\temp\qa-suivant` ; `Test-Path C:\temp\qa-suivant` répond `False`
- [ ] `C:\temp\bd-recette\etat-de-base.ps1 restaurer apres-lot1` finit par « bd-app : running » — le décor est prêt pour la passe suivante
