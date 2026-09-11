---
passe: Normaliser la casse d'une bulle
chantier: NLP-3
duree: 10 min
---

# QA — la casse se normalise par un geste, sur les bulles qui en ont besoin

La règle est verrouillée par une table de cas lue par les deux suites, Python et
navigateur. Ce que la passe regarde est ce qu'aucun test ne voit : le bouton sur de VRAIES
bulles, et **ce que la garde fait d'un OCR réel**. Mesuré sur cette base : des 31 bulles
transcrites, **4 seulement sont intégralement en capitales**. Les 27 autres portent des
minuscules parasites de l'OCR (« JE sUis LE YOTHEA… », « TU SAis… ») et le bouton y reste
éteint. C'est la garde qui joue — une ligne qui n'est pas toute en capitales n'est jamais
touchée — et non une panne ; mais cela dit ce que le geste vaudra sur ce corpus tant que
l'OCR laisse passer ces lettres.

Rappel d'un angle mort écrit dans NLP-3 : l'audit axe n'entre jamais en mode Transcription.
La dernière zone est la seule vérification d'accessibilité de ce panneau.

**Sur la pile locale**, `https://bd.127-0-0-1.sslip.io`, **sous `admin-bd`** : l'album
*Eau-terre* ne vit que dans la collection par défaut, où seule l'administration écrit. Le
geste MODIFIE le texte stocké — sans conséquence ici, la base est une copie.

**Pour entrer** : *Atelier*, album *Eau-terre*, planche 24, mode **Transcription** (touche
`T`), puis `Tab` pour passer de bulle en bulle.

### Le bouton n'est offert que s'il a quelque chose à faire

- [ ] Sur la bulle « ARRÊTEZ L'ENFANT AUSSI ! », « Normaliser la casse » est actif
- [ ] Sur la bulle « TU SAis, IL NY 4 PLUS DE… », il est éteint, et son libellé reste lisible tel quel — c'est lui qui doit dire ce qu'il ferait, l'infobulle d'un bouton éteint ne s'affichant pas partout
- [ ] Sur la planche 22, la bulle « JE sUis LE YOTHEA PHAT… » : éteint aussi, à cause du « s » et du « i » minuscules que l'OCR a laissés

### Le geste, et ce qu'il enregistre

- [ ] Cliquer sur « Arrêtez… » : la zone de saisie devient exactement « Arrêtez l'enfant aussi ! », l'accent de « Arrêtez » conservé, et l'état de sauvegarde indique l'enregistrement
- [ ] Juste après, le bouton s'est éteint : la bulle n'est plus en capitales, un second clic n'aurait rien à faire
- [ ] Le focus est resté dans la zone de saisie, à l'endroit où l'on relit et retouche
- [ ] Sur « MIT PHAT ! QU'ATTENDS - TU POUR TE SAISIR DE CET ENNEMI DE L'ANGKAR ? », la proposition est « Mit phat ! Qu'attends - tu pour te saisir de cet ennemi de l'angkar ? » — la phrase après « ! » reprend sa majuscule, et « phat » et « angkar », noms propres, restent en bas de casse : c'est la LIMITE écrite, à relever à la main, pas un échec
- [ ] Retoucher à la main en « Mit Phat ! … l'Angkar ? », passer à la bulle suivante, revenir : c'est la version retouchée qui est stockée
- [ ] Quitter la Transcription (`N`), recharger la page, y revenir : les deux bulles gardent leur texte normalisé — le geste a bien écrit, par le même chemin qu'une frappe
- [ ] Quitter la Transcription, puis Ctrl+Z dans l'Atelier : la dernière bulle modifiée retrouve son texte précédent. Si elle ne le retrouve pas, c'est un constat à remonter, pas une limite écrite

### Un stagiaire peut le faire, là où il écrit

- [ ] Sous `stagiaire`, s'il a reçu l'écriture sur « Collection Test » dans la passe *Le droit d'exporter, à l'écran* : *esther v1*, planche 1, la bulle en capitales se normalise de la même façon

### Clavier, thèmes

- [ ] Depuis la zone de saisie, `Maj+Tab` ne sort pas vers le bouton — c'est « bulle précédente » ; le bouton s'atteint à la souris, ou à la tabulation depuis « ‹ Précédent »
- [ ] En thème clair comme en sombre, le bouton ÉTEINT se distingue de l'actif, et son libellé reste lisible
- [ ] Un lecteur d'écran annonce le bouton par son libellé, et l'annonce comme indisponible quand il est éteint
