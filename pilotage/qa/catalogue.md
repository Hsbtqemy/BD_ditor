---
passe: Le catalogue de la Bibliothèque
chantier: UX-20
duree: 70 min
---

# QA — la Bibliothèque en catalogue : le rail, la grille, le volet, sous cinq comptes

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io`, reconstruite sur
`829fbb2` ou après, état `apres-ann7-j3` restauré (`C:\temp\bd-recette\etat-de-base.ps1
restaurer apres-ann7-j3`). Les mots de passe sont dans `C:\temp\bd-recette\comptes.txt`,
hors dépôt. Une fenêtre privée par identité, à 1 280 px de large sauf mention contraire.

**Ce que la passe éprouve** — l'écran d'`UX-20`, tranché par Hugo sur maquette le
2026-11-02 : les collections en RAIL, les albums au CENTRE en grille ou en liste, l'album en
VOLET à droite ; une copie repliée sous son original ; ce que l'on peut, dit en mots ; et ce
que chaque compte lit d'une copie selon ce qu'il lit de l'original. Elle **remplace**
`bibliotheque-en-calque` et `collections-bibliotheque` (Hugo, 2026-11-03), qui décrivent la
Bibliothèque d'avant.

**Le décor de l'état restauré.** Dans « Projet principal » : `proprio` est responsable et
propriétaire de « Collection Test », « Étude B », « Essai qui entre » ; `arrivant` est
propriétaire de « Carnet d'arrivant », où `stagiaire` lit ; `stagiaire` écrit dans
« Collection Test » ; `lectrice` la lit. « esther v1 » vit dans « Collection par défaut »,
« Collection Test » et « Étude B », et a une copie (faite par `admin-bd`, jusqu'à la
transcription) dans « Carnet d'arrivant ». « Annee_lievre-1 » ne vit que dans « Collection
par défaut ». « Base QA » n'a aucune planche.

**Ce que la passe ne joue pas, et où c'est éprouvé.** « Qui entre » : la passe `qui-entre`.
Prendre du fonds et dans le projet : `prendre-un-document`. Repartir de zéro et en partir :
`en-partir-d-un-travail`. Le panneau d'une planche et les mots des chemins y sont joués en
passant, pas en entier. La police de 24 et 320 px : `petites-largeurs`.

### Prélude, sous `proprio` : une copie vierge à replier
- [ ] *Bibliothèque* : le rail commence par « Tout ce que vous lisez » (le nombre d'albums à droite), puis le bloc « Collections · n » ; aucune entrée « À répondre » tant qu'aucune demande n'attend
- [ ] Ouvrir « Annee_lievre-1 » (clic sur sa carte) : le volet s'ouvre à droite, « Copie… » est dans la tête de la fiche. « Copie… » : « Copier dans » propose les collections où vous écrivez ; choisir « Collection Test », cocher « Images seules » : la phrase dit « Votre copie ira dans « Collection Test », rangée sous l'original. » ; « Copier les images » : le volet s'ouvre sur la copie, et sa fiche dit « Album · copie de travail » au-dessus du titre

### Le rail, sous `proprio`
- [ ] Le filtre au-dessus des collections a trois boutons, « Les miennes · Où j'écris · Tout », « Tout » pressé : la liste est rangée en sections « Les vôtres » (dont « Projet principal », marquée « base ») puis « Où vous lisez »
- [ ] Dans « Où vous lisez », « Collection par défaut » et « Carnet d'arrivant » portent « lecture · par le projet » ; au survol, l'infobulle dit « Vous la lisez parce que vous êtes responsable du projet »
- [ ] « Les miennes » : seules les collections dont vous êtes propriétaire, en liste simple, sans titre de section. « Où j'écris » : les mêmes ici, `proprio` n'étant en écriture nulle part ailleurs. Revenir à « Tout »
- [ ] Le petit bouton « A → Z » dans la tête du bloc : il devient « Récentes » et la liste change d'ordre ; le recliquer la remet de A à Z
- [ ] La CASE devant « Collection Test » filtre le centre sur ses albums, et le fil de la bande d'outils dit « Bibliothèque › Collection Test » ; cocher aussi « Étude B » : le fil dit « 2 collections filtrées », et un choix « Montrer : Dans l'une · Dans toutes » apparaît. Décocher les deux
- [ ] Le NOM « Collection Test » (et non sa case) ouvre la collection : le centre devient sa fiche, onglet *Albums*, avec son catalogue

### Le centre : grille, liste, couvertures
- [ ] « Tout ce que vous lisez » : les albums s'affichent en GRILLE de cartes de même taille, chacune avec une couverture réduite et son titre ; « Base QA » montre son titre sur un aplat, sans image
- [ ] « ☰ Liste » : une ligne par album, avec une petite couverture, les planches, les validées et la colonne « Vit dans » ; la ligne d'« esther v1 » dit « Collection par défaut · Collection Test · Étude B ». F5 : la liste est restée (le choix est retenu sur le poste). Revenir à « ▦ Grille »
- [ ] Ouvrir « Collection Test » par son nom, en liste : dans « Vit dans » d'« esther v1 », « Collection Test » est en gras
- [ ] « Lot TIFF QA » porte la marque « à vous » (au survol : « Vous avez importé cet album ») ; « Collection par défaut » étant lue seulement, « Eau-terre » porte la marque « lecture »

### Une copie repliée sous son original, sous `proprio`
- [ ] « Tout ce que vous lisez », grille : « Annee_lievre-1 » est une PILE, avec « ▸ 1 copie » sous la carte ; la copie du prélude n'a pas de carte à elle
- [ ] « ▸ 1 copie » : il devient « ▾ 1 copie », et une carte « Votre copie » suit l'original, avec « copie vierge » et la marque « à vous » ; le titre « Annee_lievre-1 » n'y est pas répété
- [ ] « esther v1 » est aussi une pile ; dépliée, sa copie s'appelle « Copie de travail », avec « copie · jusqu'à la transcription » : `proprio` ne fait que la LIRE (par le projet), le nom de qui l'a faite ne lui est pas dit
- [ ] Ouvrir « Collection Test » par son nom : « Annee_lievre-1 », qui n'y vit pas, est là quand même, ÉTEINT, « hors de cette collection », sans case à cocher ni marque, et sa copie « Votre copie » est dessous

### Le volet, sous `proprio`
- [ ] « Tout ce que vous lisez », ouvrir « Eau-terre » : le volet occupe à peu près la moitié droite, le catalogue reste à gauche, resserré ; les cartes gardent LEUR taille (il y en a moins par rangée), et « Eau-terre » reste visible dans le catalogue
- [ ] La fiche dit « Album » au-dessus du titre, puis le nombre de planches, et les actes « lire », « annoter », « exporter », seul « lire » marqué comme possible (vous ne faites que lire « Collection par défaut ») ; aucun « ✎ Modifier » ni « ✔ Tout valider »
- [ ] Le fil de la bande d'outils dit « Bibliothèque › Eau-terre »
- [ ] « Fermer ✕ » : le volet se ferme, le catalogue reprend toute la largeur, et le focus clavier revient sur la carte d'« Eau-terre »
- [ ] Ouvrir la copie « Votre copie » d'« Annee_lievre-1 » : le fil dit « Bibliothèque › Annee_lievre-1 › Votre copie », et l'adresse porte `?album=<id>`. Copier cette adresse dans un nouvel onglet : la même fiche s'ouvre dans le volet
- [ ] Dans la fiche de cette copie : « ✎ Modifier », « ✔ Tout valider » et « Copie… » dans la tête, puis « Autres gestes ▾ » ; le déplier : « Repartir de zéro… », « Retirer du projet… » et « Supprimer… »
- [ ] Le bloc « Ce document · 2 versions lues » : « L'original », un lien qui ouvre « Annee_lievre-1 », et « Votre copie (ici) »
- [ ] Le bloc « Sur les collections » : une case par collection du projet que vous lisez, « Collection Test » cochée

### Sous `stagiaire` : écrire sans tenir l'espace
- [ ] *Bibliothèque*, « Tout » : « Collection Test » est sous « Où vous écrivez », « Carnet d'arrivant » sous « Où vous lisez », avec « écriture » et « lecture » ; aucune section « Les vôtres »
- [ ] « Tout ce que vous lisez » : la copie du prélude est SEULE, sur sa propre carte, nommée « Copie de » suivi du nom de `proprio`, avec « copie vierge » : `stagiaire` ne lit pas « Annee_lievre-1 », que rien ne nomme ni ne situe
- [ ] Ouvrir « esther v1 », « Autres gestes ▾ », « Supprimer… » : la réponse définitive dit « La demande part à » `proprio` (son nom lisible), « responsable du projet, qui décide. » ; motif « QA catalogue », cocher la certification, « Envoyer la demande » : la fiche dit que sa suppression est demandée

### Sous `lectrice` : lire
- [ ] *Bibliothèque* : aucune collection n'est marquée « propriétaire », et « + Créer une collection », s'il paraît, est éteint ; « Collection Test » porte « lecture »
- [ ] La copie du prélude est seule, nommée « Copie de travail », avec « copie vierge » : ni le nom de qui l'a faite, ni l'original
- [ ] Toutes les cartes de « Collection Test » portent la marque « lecture » ; ouvrir un album : la liste des actes dit « lire » oui, « annoter » et « exporter » non, et il n'y a ni « ✎ Modifier », ni « Autres gestes ▾ »

### Sous `arrivant` : la copie d'un original qu'on ne lit pas
- [ ] « Carnet d'arrivant » ouvert par son nom : la copie d'« esther v1 » est SEULE, nommée « Copie de » suivi du nom d'`admin-bd`, avec « copie · jusqu'à la transcription » ; l'ouvrir : aucun bloc « Ce document »

### Retour sous `proprio` : « À répondre »
- [ ] Le rail : sous « Tout ce que vous lisez », « À répondre » est apparu, avec « ⚑ 1 », et la bande d'outils porte un rappel « 1 demande d'effacement »
- [ ] « À répondre » : le centre montre « Demandes d'effacement · 1 » ; la ligne d'« esther v1 » nomme `stagiaire`, le motif « QA catalogue », et « qui perd quoi » déplié. « Garder » : la ligne quitte le bloc, et « À répondre » dit « 0 » dans le rail

### Sous `admin-bd` : la portée totale
- [ ] *Bibliothèque* : le rail commence par « Tout le projet » ; le bloc Collections n'a ni filtre ni sections, et les collections portent « administrateur »
- [ ] La copie du prélude, dépliée sous « Annee_lievre-1 », s'appelle « Copie de » suivi du nom de `proprio`

### Petites largeurs et clavier, sous `proprio`
- [ ] Fenêtre à 900 px de large (moins de 60em), « Tout ce que vous lisez », ouvrir un album : le volet PREND LA PLACE du catalogue au lieu de le resserrer ; « Fermer ✕ » rend le catalogue
- [ ] Outils de développement à 700 px (moins de 46em) : le rail laisse place à une liste *Collection* et à un bouton « Collections… », qui rouvre le rail
- [ ] À pleine largeur, au clavier seul : Tab atteint « Tout ce que vous lisez », la case puis le nom de chaque collection, le filtre, « ☰ Liste / ▦ Grille », puis les cartes ; Entrée sur une carte ouvre le volet et met le focus sur le titre de la fiche ; « Fermer ✕ » au clavier rend le focus à la carte

### Remise en état
- [ ] **Sous `proprio`**, ouvrir « Votre copie » d'« Annee_lievre-1 », « Autres gestes ▾ », « Supprimer… », « Supprimer définitivement » : la copie part sans demande, et « Annee_lievre-1 » n'est plus une pile
- [ ] *Bibliothèque*, « ▦ Grille » est la vue retenue (sinon, la cliquer : les passes suivantes l'attendent)
