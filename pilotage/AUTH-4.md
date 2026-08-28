---
chantier: AUTH-4
statut: à venir
---

# AUTH-4 — le référent d'un espace : nommer l'administrateur plutôt que le taire

**Point de départ** — fiche ouverte le 2026-08-28 au fil d'une conversation de conception,
avant tout code. Le constat : un administrateur (`bd-admins`) lit et écrit toute
collection **sans jamais y figurer**. `clause_album()` renvoie `"1", []` quand la portée
est totale — la requête ne consulte pas `collection_album`, et `collection_acces` ne porte
aucune ligne le concernant, sur aucune collection. Son accès n'est donc pas un droit
accordé, c'est un court-circuit en amont de la table.

Ce n'est pas un défaut : c'est la vérité de tout système auto-hébergé, et il télécharge
`GET /api/sauvegarde` de toute façon. Mais entre « ce pouvoir est inévitable » et « ce
pouvoir est invisible » il y a un écart, et c'est le seul qu'on puisse fermer. Le chantier
ne retire donc rien à personne : il donne un **visage** à un pouvoir qui n'en a pas.

## Reste

### Arbitrages
- [ ] Qui désigne le référent est tranché : le propriétaire de la collection (il choisit son interlocuteur, au risque de nommer quelqu'un qui n'a aucun pouvoir sur l'instance) ou l'administrateur lui-même (exact, moins souple). Les deux se défendent, un seul se code
- [ ] Ce qu'on stocke est tranché : un login seul ne permet d'écrire à personne. Nom + moyen de contact, ou renvoi vers une page d'instance
- [ ] Le sort de `collection.responsables` est tranché : le patron convient (JSON `[{nom, role, orcid}]`, `role` contrôlé-ouvert) mais le champ est SCIENTIFIQUE — il porte un ORCID et il part au dépôt Nakala, où un référent technique n'a rien à faire. Réutiliser ou créer, pas les deux
- [ ] L'existence d'un référent d'instance PAR DÉFAUT (variable d'environnement) est tranchée : c'est le seul qui puisse s'afficher à qui n'a encore aucune collection — donc le seul qui serve le bandeau de portée vide, qui est pourtant le cas le plus criant

### Le fait à déclarer
- [ ] Le panneau des accès d'une collection cesse de mentir par omission : il déclare que les administrateurs de l'instance lisent et écrivent toute collection. Aujourd'hui `_acces_de()` ne lit que `collection_acces` — la liste affiche trois noms là où quatre personnes lisent, et l'écran protège soigneusement cette liste au motif que « la liste des membres d'une étude est une donnée sur des personnes » (`static/corpus.js:684`)
- [ ] Le bandeau de portée vide nomme un destinataire : `static/theme.js:232` envoie déjà une personne BLOQUÉE « demander un accès à un administrateur de l'instance », sans lui dire à qui s'adresser. C'est l'endroit où un référent sert vraiment — avant le panneau des accès, qui n'est vu que par des gens que rien ne bloque
- [ ] Les noms de groupes de `BD_AUTH_ADMIN_GROUPS` sortent par une route (le bloc `acces` de `GET /api/moi` est le candidat) : ce ne sont pas des secrets — ils sont en clair dans `deploy/docker-compose.yml` — mais aucune route ne les dit, si bien qu'une personne admise ne peut pas même déduire que le groupe existe

### Vérifications
- [ ] `autorisation.py` n'apparaît pas dans le diff du chantier : un référent est une ADRESSE et non un droit. S'il y entre, c'est qu'on a glissé vers le cloisonnement entre administrateurs, écarté ici
- [ ] Le cas du référent périmé est documenté et assumé : un référent qui a quitté `bd-admins` reste affiché, parce que l'application ne connaît les groupes que de la personne qui frappe, à l'instant de sa requête (AUTH-1). L'appartenance d'un TIERS lui est structurellement invérifiable — la déclaration est donc déclarative, et le dire vaut mieux que le laisser découvrir

## Contexte

**Deux lectures de « un administrateur dédié à tel espace », et une seule tient.**

*Comme adresse* — un référent est une propriété de la **collection**, jamais de
l'administrateur : l'application ne stocke aucune appartenance de groupe (invariant
AUTH-1), elle ne lit `Remote-Groups` que pour la personne présente. Un champ, un
affichage, et la zone qui décide « qui voit quoi » reste intacte. C'est le critère de
réussite du chantier, d'où la case de vérification sur `autorisation.py`.

*Comme barrière* — « A administre la collection 1, B la 2, et A ne voit pas la 2 » : cher,
et surtout FAUX. Les deux gardent `GET /api/sauvegarde`, entière par décision de DROIT-1
(« une sauvegarde partielle ne restaure pas une instance »), plus le fichier SQLite et le
shell. On afficherait une garantie qu'on ne peut pas tenir, ce qui est pire que de ne rien
afficher. **Écarté avant d'être commencé** — et c'est la raison d'être de la case de
vérification : le glissement se ferait sans qu'on le décide.

**Ce que le chantier suppose déjà fait, et qui l'est.** Le code refuse déjà de confondre
un administrateur et un propriétaire, dans les deux sens : le badge de l'écran Collections
affiche « Administrateur » et jamais « Propriétaire », parce que « le dire à un
administrateur lui ferait croire à un lien personnel avec une collection qui n'est pas la
sienne » (`static/corpus.js:690`) ; un administrateur qui crée une collection n'en devient
pas propriétaire (`main.py:2560`) ; et la garde du dernier propriétaire porte sur l'ÉTAT
et non sur l'acteur, si bien qu'un administrateur ne peut pas évincer un propriétaire d'un
seul geste — il doit d'abord en désigner un autre, ce qui laisse deux événements
`lien`/`delien` au journal. AUTH-4 continue cette ligne : il ne crée pas la distinction,
il la rend LISIBLE à celui qu'elle protège.

**La garantie existe déjà, elle est juste illisible.** Chaque fois qu'un administrateur
entre dans une collection, `evenement.agent` le nomme — le journal A3 enregistre l'acte,
append-only, avec son avant/après. Mais AUCUNE route HTTP ne lit `evenement` : les seuls
`SELECT` du dépôt sont dans `undo.py`, et encore uniquement pour retrouver MON dernier
acte annulable. Consulter le journal demande un accès shell. Le contre-pouvoir réel du
propriétaire de collection — voir QUAND l'administrateur est entré, et pas seulement
savoir qu'il le peut — dépend donc d'une surface d'audit qui n'existe pas. C'est un
chantier voisin et distinct, non ouvert à ce jour ; AUTH-4 tient sans lui, et gagnerait
beaucoup avec.

**`à venir` plutôt que `différé`** : rien ne bloque techniquement, aucun autre chantier
n'a besoin d'aboutir d'abord. Les arbitrages ci-dessus deviendront simplement plus faciles
à trancher à mesure que l'usage multi-utilisateur devient réel (piste C) — on saura alors
qui écrit à qui, et pourquoi. Ouvrir maintenant sert surtout à ce que le raisonnement ne
reste pas dans une conversation.
