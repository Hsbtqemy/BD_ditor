---
passe: Normaliser la casse d'une bulle
chantier: NLP-3
duree: 10 min
derniere: —
---

# QA — la casse se normalise par un geste, sur les bulles qui en ont besoin

La règle est verrouillée par une table de cas lue par les deux suites, Python et
navigateur. Ce que la passe regarde est ce qu'aucun test ne voit : le bouton sur de VRAIES
bulles, et **ce que la garde fait d'un OCR réel**.

**Remesuré le 2026-09-14, et la première rédaction était fausse.** Elle annonçait « 4 bulles
en capitales, les 27 autres à minuscules parasites », ce qui faisait de la garde un obstacle
général et rendait la passe peu probante. Les 31 bulles font **trois** populations, pas deux :

- **4 intégralement en capitales** — le bouton est actif (régions 25, 136, 139, 142) ;
- **3 à minuscules PARASITES**, de 3,9 % à 6,2 % des lettres : 137 « TU SAis… » (3 sur 76),
  138 « "GRAND FRÈRE", REGARDE ! … » (2 sur 45), 141 « JE sUis LE YOTHEA… » (10 sur 161).
  Le bouton y est éteint pour une poignée de caractères, et c'est LE cas intéressant ;
- **24 réellement mixtes**, de 14,8 % à 100 % — « Hey Abdou 1 C'est quo1 "PÉDÉ" ? »,
  « c'était trop bien ! ». Le bouton doit y être éteint : ce n'est pas du lettrage capital
  abîmé, c'est de la casse ordinaire.

**Les deux dernières populations ne se recouvrent pas** : 6,2 % puis 14,8 %, et rien entre
les deux. La garde ne coûte donc que sur TROIS bulles de ce corpus. C'est la garde qui joue
— une ligne qui n'est pas toute en capitales n'est jamais touchée — et non une panne.

Rappel d'un angle mort écrit dans NLP-3 : l'audit axe n'entre jamais en mode Transcription.
La dernière zone est la seule vérification d'accessibilité de ce panneau.

**Sur la pile locale**, `https://bd.127-0-0-1.sslip.io`, **sous `admin-bd`** : l'album
*Eau-terre* ne vit que dans la collection par défaut, où seule l'administration écrit. Le
geste MODIFIE le texte stocké — sans conséquence ici, la base est une copie.

**Pour entrer** : *Atelier*, album *Eau-terre*, planche 24, mode **Transcription** (touche
`T`), puis `Tab` pour passer de bulle en bulle.

### Le bouton n'est offert que s'il a quelque chose à faire

- [x] Sur la bulle « ARRÊTEZ L'ENFANT AUSSI ! », « Normaliser la casse » est actif
- [x] Sur la bulle « TU SAis, IL NY 4 PLUS DE… », il est éteint, et son libellé reste lisible tel quel — c'est lui qui doit dire ce qu'il ferait, l'infobulle d'un bouton éteint ne s'affichant pas partout
- [x] Sur la planche 22, la bulle « JE sUis LE YOTHEA PHAT… » : éteint aussi — 10 lettres minuscules sur 161, dont le « s » et le « i » de « sUis ». Les autres sont plus loin dans la bulle : le compte ne se lit pas sur les premiers mots

### Le geste, et ce qu'il enregistre

- [x] Sur la bulle « ARRÊTEZ L'ENFANT AUSSI ! » — planche 24, celle de la première case — cliquer sur le bouton « Normaliser la casse », dans la barre SOUS la zone de saisie, entre « ‹ Précédent » et « Valider + Suivant › ». Il n'y a pas de bouton « Arrêtez » : c'est le nom de la bulle. La zone de saisie devient alors exactement « Arrêtez l'enfant aussi ! », l'accent de « Arrêtez » conservé, et l'état de sauvegarde indique l'enregistrement
- [x] Juste après, le bouton s'est éteint : la bulle n'est plus en capitales, un second clic n'aurait rien à faire
- [x] Le focus est resté dans la zone de saisie, à l'endroit où l'on relit et retouche
- [x] Toujours planche 24, `Tab` jusqu'à « MIT PHAT ! QU'ATTENDS - TU POUR TE SAISIR DE CET ENNEMI DE L'ANGKAR ? », puis de nouveau « Normaliser la casse » : la proposition est « Mit phat ! Qu'attends - tu pour te saisir de cet ennemi de l'angkar ? » — la phrase après « ! » reprend sa majuscule, et « phat » et « angkar », noms propres, restent en bas de casse : c'est la LIMITE écrite, à relever à la main, pas un échec
- [x] Retoucher à la main en « Mit Phat ! … l'Angkar ? », passer à la bulle suivante, revenir : c'est la version retouchée qui est stockée
- [x] Quitter la Transcription (`Échap`, ou le bouton « Quitter »), recharger la page, y revenir : les deux bulles gardent leur texte normalisé — le geste a bien écrit, par le même chemin qu'une frappe
- [x] Quitter la Transcription, puis Ctrl+Z dans l'Atelier : la dernière bulle modifiée retrouve son texte précédent. Si elle ne le retrouve pas, c'est un constat à remonter, pas une limite écrite

### Un stagiaire peut le faire, là où il écrit

- [x] Sous `stagiaire`, qui écrit sur « Collection Test » depuis la passe *Le droit d'exporter, à l'écran* — vérifié le 2026-09-14, et s'il ne l'a plus, lui accorder l'écriture d'abord : *esther v1*, planche 1, la bulle « PÉDÉ ! » est intégralement en capitales et se normalise de la même façon

### Clavier, thèmes

- [x] Depuis la zone de saisie, `Maj+Tab` ne sort pas vers le bouton — c'est « bulle précédente » ; le bouton s'atteint à la souris, ou à la tabulation depuis « ‹ Précédent »
- [x] Les deux raccourcis de mode font ce qu'ils annoncent, et RIEN d'autre : depuis l'Atelier, `T` ouvre la Transcription sans écrire « t » dans la première bulle ; depuis la Transcription, `Échap` en sort sans écrire « échap » ni rien. Les deux écrivaient leur caractère dans le texte avant le 2026-09-14, et l'enregistraient 500 ms plus tard sans qu'aucun autre geste soit fait
- [x] En thème clair comme en sombre, le bouton ÉTEINT se distingue de l'actif, et son libellé reste lisible
- [x] Un lecteur d'écran annonce le bouton par son libellé, et l'annonce comme indisponible quand il est éteint
