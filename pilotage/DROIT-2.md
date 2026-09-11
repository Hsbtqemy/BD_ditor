---
chantier: DROIT-2
statut: à venir
---

# DROIT-2 — exporter est un droit à part, accordé par collection

**Point de départ** — 2026-09-11, pendant COL-2. À la question « le bloc d'export suit-il
les descripteurs vers la Bibliothèque ? », l'équipe a répondu : *« tout dépend de qui a
accès à cela. L'export reste quelque chose de particulièrement sensible, et il ne faut pas
que tout le monde y ait accès. »* Mesuré dans la foulée : **aujourd'hui, toute personne qui
peut LIRE une collection peut en exporter le contenu, texte relevé compris.**

Tranché le même jour, en deux temps : **exporter devient un droit à part** — ni un niveau,
ni un réglage de l'écran —, et il s'accorde **par collection**, par une case à côté du
niveau d'accès, **d'office pour les propriétaires**.

## Les dix portes, mesurées le 2026-09-11

| porte | où | ce qui sort | garde aujourd'hui |
|---|---|---|---|
| Export de dépôt — fiche, enregistrements, manifeste IIIF | bloc de collection | métadonnées, et le **texte relevé** si la case est cochée | lire |
| Dépôt ShareDocs de ces mêmes exports | idem | idem | propriétaire |
| JSON, CSV, TEI d'un album | menu de l'Atelier | l'album entier, texte relevé compris | lire |
| CSV de la Recherche | Recherche | résultats, texte relevé, notes, tags | lire |
| Six CSV de l'Exploration | Exploration | fréquences, **concordances** (du texte), comparaison, croisement, accords | lire — sauf l'accord inter-annotateurs, qui exige d'écrire |
| Panier de figures | Atelier | recadrages d'images, avec leur légende | lire |
| Sauvegarde | Administration | toute la base | administrateurs |

**Pourquoi c'était ouvert, et c'était écrit.** EXP-1 : *« décrire une collection qu'on lit
n'est pas la partager »* — la garde commune des trois exports de dépôt est LIRE. DROIT-1
(arbitrage du 2026-08-28) : à l'intérieur de l'instance, le régime de diffusion ne borde
rien, parce que l'annotation repose sur les images et que le travail interne relève de
l'usage savant. Ces deux décisions restent vraies de ce qu'elles décrivent : voir, annoter,
travailler.

**Pourquoi ça cesse.** Télécharger n'est pas travailler dans l'instance : c'est SORTIR. Le
fichier quitte l'instance pour un poste qu'elle ne contrôle plus, et la base légale du
corpus n'est toujours pas établie (`DEPOT-1`). C'est l'axe DEDANS / DEHORS de DROIT-1,
appliqué à une sortie qu'il n'avait pas nommée — pas un retour au classement des personnes
par niveau, que DROIT-1 a écarté.

**Pourquoi un droit à part, et pas un niveau.** Les stagiaires sont en écriture, et c'est
voulu : une règle « écriture et plus » ne les arrêterait pas. Exporter ne s'ordonne pas
avec annoter, et c'est exactement le cas qu'`AUTH-10` avait décrit — une capacité hors de
l'échelle `lecture ⊂ ecriture ⊂ proprietaire`. Sa conclusion structurelle était qu'une
telle capacité serait **un drapeau de plus, pas un changement de modèle** : ce chantier est
le premier à l'éprouver.

## Reste

### Le modèle
- [ ] **Une colonne booléenne `exporter` sur `collection_acces`**, par migration (incrément de `SCHEMA_VERSION` et étape de `_migrate()`), défaut faux. Le niveau reste une seule valeur ordonnée : la case s'y ajoute sans y entrer, et le cumul des niveaux reste dérivé à un seul endroit
- [ ] **`Portee` gagne un ensemble `export` et une question `peut_exporter(collection_id)`** : les propriétaires, les lignes cochées, et tout pour un administrateur comme en mono-poste. `autorisation.py` reste le seul endroit qui tranche — une deuxième règle dans une route serait la divergence à venir
- [ ] **Accorder ou retirer le droit est un geste de PROPRIÉTAIRE** (`peut_administrer`). Décider ce qui sort engage la collection autant que décider qui entre
- [ ] **Le changement est tracé au journal A3**, comme les autres changements d'accès

### Les portes
- [ ] **Les dix portes exigent `peut_exporter`, sauf la sauvegarde**, qui reste aux administrateurs. Le dépôt ShareDocs garde son exigence de propriétaire EN PLUS : envoyer dans un dossier partagé que l'application ne contrôle pas n'est pas le même geste que télécharger pour soi
- [ ] **Un export qui traverse plusieurs collections filtre par droit d'EXPORTER, pas par droit de LIRE.** La Recherche et l'Exploration portent sur tout ce qu'on lit ; sans ce filtre, qui exporte la collection A emporterait le texte de B dans une concordance qui couvre les deux. `Portee` doit donc offrir une clause d'export, analogue à `clause_album`, et les deux cœurs partagés (`_recherche_rows`, `_analyse_filtres`) doivent pouvoir la recevoir
- [ ] **L'export d'un ALBUM a une ambiguïté, et elle se tranche avant d'écrire** : un album vit dans plusieurs collections depuis AUTH-3, et le droit peut être accordé sur l'une et pas sur l'autre. « Au moins une » est permissif ; « toutes » ferme un album dès qu'il est rangé dans une seconde collection. DROIT-1 a déjà rencontré cette question pour le manifeste IIIF, et y a répondu en exigeant que la collection soit NOMMÉE
- [ ] **Le panier de figures en fait partie.** DROIT-1 dit que citer n'est jamais bloqué par le RÉGIME de diffusion, et ça reste vrai : qui a le droit d'exporter cite, même depuis une collection sous embargo. Ce qui change est QUI peut exporter, pas ce que le régime retient
- [ ] **Un cliquet énumère les portes, parce que l'oubli d'une garde échoue ici OUVERT.** Toute route qui produit un fichier téléchargeable doit consulter `peut_exporter`, ou être déclarée avec sa raison. Une porte oubliée continuerait de laisser sortir — c'est précisément l'état d'aujourd'hui, et il ne ferait tomber aucun test. Même forme que le cliquet des sorties d'identité d'AUTH-5, et même exigence d'un plancher dérivé du source (ARCH-2)

### L'écran
- [ ] **Une case « peut exporter » dans le panneau des accès**, à côté du niveau, libellée par l'ACTE et non par un nom de niveau — c'est l'exigence qu'AUTH-10 a posée pour ses cases. Chez un propriétaire, elle apparaît cochée et non modifiable, avec la raison écrite à côté
- [ ] **`GET /api/collections` porte `exportable`**, comme il porte `administrable`. Les boutons d'export se cachent pour qui n'a pas le droit ; la garde reste celle du serveur, et l'écran ne fait qu'éviter de proposer un geste qu'il refusera
- [ ] **Un refus d'export est un 403 NOMMÉ, pas un 404** : l'objet est lisible — on vient de l'afficher —, donc un 404 mentirait. C'est la précision qu'AUTH-10 a écrite pour les refus d'écriture sur un objet visible

### Ce qui devra être vrai
- [ ] Un compte en écriture, sans la case, n'exporte rien : ni le TEI de l'Atelier, ni une concordance, ni une figure — éprouvé sous son identité, porte par porte
- [ ] Le même compte, case cochée sur la collection A, exporte A et pas B, y compris dans une concordance qui traverse les deux
- [ ] Un propriétaire exporte sa collection sans avoir rien à cocher
- [ ] Le mono-poste est inchangé : sans proxy, la portée est totale, export compris

## Contexte

**Ordre imposé par la session voisine.** Ce chantier touche `routes/analyse.py`,
`routes/recherche.py` et probablement `socle.py`, que `ANA-6` modifie au même moment. Il
passe donc après les commits d'ANA-6 sur ces fichiers ; la session concernée est prévenue,
et son export de concordance — qui existe depuis ANA-7, ANA-6 n'y ajoutant que deux colonnes,
les tags et la note — suit la règle commune plutôt qu'une garde à part.

**Ce que COL-2 en fait.** Le bloc d'export de collection déménage TEL QUEL dans la
Bibliothèque ; ce chantier-ci pose ensuite sa garde au serveur et `exportable` à l'écran,
à un seul endroit. Faire l'inverse — restreindre le bloc pendant le déménagement — aurait
laissé les neuf autres portes ouvertes en donnant l'impression d'avoir fermé.

**Voisinage.** `DROIT-1` (DEDANS / DEHORS, et le patron « nommer la collection »), `EXP-1`
(la décision « décrire n'est pas partager », rouverte ici pour la sortie), `AUTH-10` (la
capacité hors de l'échelle, dont ceci est le premier cas réel), `AUTH-2` / `AUTH-3` (la
portée et ses deux cœurs partagés), `AUTH-5` (le patron du cliquet des sorties),
`DEPOT-1` (la base légale non établie, qui rend la question pressante), `ANA-6` (l'export
de concordance, en cours), `COL-2` (le déménagement du bloc).
