---
passe: Le droit d'exporter, à l'écran
chantier: DROIT-2
duree: 35 min
---

# QA — exporter est une case à côté du niveau, et chaque surface la suit

La suite verrouille le serveur : quinze portes sous un cliquet, chacune jouée avec et sans
la case, et quatre tests navigateur. Ce qu'elle ne voit pas, c'est **ce que l'écran DIT** à
qui n'a pas le droit — une note qui explique, ou un bouton qui disparaît sans un mot — et
l'effet de la migration sur une base qui a VÉCU. C'est ce que cette passe regarde.

**Elle se joue sur la pile locale complète** (Caddy, Authelia, annuaire, image `runtime`),
à l'adresse `https://bd.127-0-0-1.sslip.io`. Le certificat est signé par Caddy lui-même
(`tls internal`) : le navigateur avertit, on accepte. Une fenêtre de navigation PRIVÉE par
identité, ou une déconnexion entre deux, sans quoi la session de la précédente reste.

**La base est une copie de la base locale, restée en v25 comme la production**, dans
laquelle on a posé AVANT la migration les accès de la forme de la production :

| Identité | Ce qu'elle est sur « Collection Test » |
|---|---|
| `admin-bd` | groupe `bd-admins` : voit et administre tout |
| `proprio` | propriétaire, posé avant la migration |
| `lectrice` | lecture, par le groupe `annotateurs`, posé avant la migration |
| `stagiaire` | rien encore : son accès en écriture se pose pendant la passe |

« Collection Test » contient l'album **esther v1**, qui vit aussi dans la collection par
défaut. Le groupe `etudiants` y a aussi l'écriture, posée avant la migration pour la passe
d'AUTH-6 : il sert ici de témoin. Au démarrage, l'image a migré la base jusqu'à v28 : la première zone vérifie que la
v27 a fait ce que la production va vivre.

### La migration a fermé l'export à qui lisait

**Sous `admin-bd`**, *Administration → 👥 Accès aux collections*, « Collection Test ».

- [ ] L'accès de `proprio` porte la case « peut exporter » COCHÉE et grisée, suivie de « (d'office, en propriétaire) »
- [ ] L'accès du groupe `annotateurs` porte la case « peut exporter » DÉCOCHÉE : la migration n'a rien rattrapé, et c'est ce qui arrivera au groupe réel de la production
- [ ] L'accès du groupe `etudiants`, en ÉCRITURE, porte lui aussi la case décochée : écrire n'y suffit pas plus que lire
- [ ] La ligne d'ajout d'un accès porte elle aussi une case « peut exporter », décochée

### Sans la case, aucune surface ne propose d'exporter

**Sous `lectrice`.** Chaque case dit ce qui MANQUE, et aucune surface ne laisse un bouton
qui échouerait au clic.

- [ ] *Bibliothèque → 📚 Collections → « Collection Test »* : le bloc « Export de dépôt » n'a aucun bouton, et dit « Exporter cette collection demande le droit d'exporter, que son propriétaire accorde accès par accès : la lire n'y suffit pas. »
- [ ] *Atelier*, album esther v1, menu ☰ → *Exporter* : ni « Export JSON-LD », ni « Export CSV », ni « Export TEI P5 » ; à leur place une entrée « Exporter : droit manquant… »
- [ ] Cette entrée, cliquée, affiche « Exporter cet album demande le droit d'exporter l'une de ses collections, que son propriétaire accorde accès par accès : le lire ou l'annoter n'y suffit pas. »
- [ ] *Atelier*, une région sélectionnée : le bouton « ＋ Figure » n'apparaît pas
- [ ] *Recherche* : pas de bouton d'export CSV, et sous la barre la note « Exporter demande un droit que le propriétaire d'une collection accorde : vous ne l'avez sur aucune de celles que vous lisez. »
- [ ] *Exploration* : aucun des trois « ⤓ Exporter (CSV) » — sous la vue, dans 🎯 Accord, dans 👥 Inter —, et la même note
- [ ] L'adresse d'un export tapée à la main, `https://bd.127-0-0-1.sslip.io/api/export/csv?album_id=2`, répond un refus qui DIT ce qui manque (« Exporter demande le droit d'exporter… »), et non une page vide ni « introuvable »

### La case cochée rend l'export

**Sous `proprio`**, puis sous `lectrice` après s'être reconnecté.

- [ ] Sous `proprio`, *Administration → 👥 Accès aux collections*, « Collection Test » : cocher « peut exporter » sur le groupe `annotateurs` ; l'écran se recharge, et la case est toujours cochée — c'est ce que le serveur a enregistré, pas ce qu'on a cliqué
- [ ] Sous `lectrice` : les trois formats reviennent dans le menu de l'Atelier, et « Exporter : droit manquant… » a disparu
- [ ] « Export CSV » télécharge `album_2_c2.csv` — le nom dit au titre de quelle collection l'album est sorti
- [ ] « Export JSON-LD » ouvert, le champ `exporte_au_titre_de` nomme « Collection Test »
- [ ] *Recherche* et *Exploration* retrouvent leurs boutons d'export, SANS note : la lectrice exporte tout ce qu'elle lit
- [ ] *Bibliothèque* : le bloc « Export de dépôt » de « Collection Test » montre ses lignes et ses boutons, sans la ligne « Déposer sur ShareDocs », qui reste au propriétaire

### Annoter n'est pas exporter

**Sous `proprio`, puis sous `stagiaire`.** C'est le cas qui a fait naître le chantier : les
stagiaires annotent, ils ne sortent pas le texte.

- [ ] Sous `proprio`, accorder à l'utilisateur `stagiaire` l'**écriture** sur « Collection Test », case « peut exporter » laissée décochée
- [ ] Sous `stagiaire` : modifier la note d'une région d'esther v1 s'enregistre
- [ ] Sous `stagiaire` : le menu *Exporter* de l'Atelier n'offre que « Exporter : droit manquant… », et la Recherche porte la note du droit manquant

### Deux collections exportables : choisir

**Sous `proprio`.**

- [ ] *Bibliothèque → 📚 Collections* : créer « Étude B » ; elle apparaît avec `proprio` pour propriétaire, et le message qui suit la création dit où faire entrer quelqu'un
- [ ] Rattacher l'album esther v1 à « Étude B » depuis sa fiche dans la Bibliothèque ; il vit alors dans trois collections, dont deux que `proprio` peut exporter
- [ ] *Atelier*, esther v1, « Export JSON-LD » : une fenêtre « Exporter au titre de quelle collection ? » propose « Collection Test » et « Étude B », et pas la collection par défaut
- [ ] Dans cette fenêtre, Tab ne sort pas de la fenêtre ; Échap la ferme, et le focus revient sur un élément VISIBLE de l'Atelier, avec son contour — pas sur le corps de la page, le menu d'où l'on venait s'étant refermé
- [ ] Choisir « Étude B » puis *Exporter* : le JSON-LD porte `exporte_au_titre_de` nommant « Étude B »
- [ ] Accorder au groupe `annotateurs` la **lecture** sur « Étude B », case décochée. Sous `lectrice`, la Recherche dit alors « Le fichier n'emporte que les collections que vous pouvez exporter : l'écran peut en montrer davantage. »

### Étroit, clavier, thèmes

**Sous `proprio`**, qui voit les cases et la fenêtre de choix.

- [ ] À 375 px, dans les accès, la case « peut exporter » et son libellé passent à la ligne sans faire déborder la page de côté
- [ ] La case s'atteint à la tabulation, avec un contour de focus visible, et un lecteur d'écran l'annonce avec le nom de l'accès (« annotateurs peut exporter »)
- [ ] En thème clair comme en sombre, la note du droit manquant (Recherche, Bibliothèque) se lit sans effort, et ne tient pas à la seule couleur
