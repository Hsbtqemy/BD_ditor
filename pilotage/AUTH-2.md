---
chantier: AUTH-2
statut: différé
---

# AUTH-2 — un point de passage unique pour l'autorisation

**Point de départ** — mis en attente derrière AUTH-1 : il n'y a rien à autoriser tant
qu'il n'y a pas d'utilisateur. Aucune ligne écrite.

## Reste

### Le passage obligé
- [ ] Une dépendance unique répond « quelles collections cette requête a-t-elle le droit de voir, et en écriture ou en lecture », et c'est le SEUL endroit du code où cette question se tranche
- [ ] Les 93 points `Depends(db)` de `main.py` passent par elle, ou bien sont recensés par écrit comme délibérément hors périmètre (santé, statiques, `/api/moi`)
- [ ] Un test échoue si une nouvelle route accède aux données sans passer par le point de passage — sinon l'oubli d'une seule route est une fuite silencieuse, et il y a 110 routes

### Les endroits où ça fuit d'habitude
- [ ] La recherche FTS ne renvoie que des régions de collections autorisées : la table `recherche` est dénormalisée et globale, elle ne connaît ni album ni collection
- [ ] Les surfaces d'analyse (fréquences, concordance, croisement, comparaison, accord, accord inter) sont filtrées par le même point de passage, pas chacune à sa façon
- [ ] Un album n'appartenant à AUCUNE collection a un sort tranché et écrit (visible de tous, ou de personne)
- [ ] Les exports et le manifeste IIIF n'exposent pas ce que l'UI cache

## Contexte

**C'est l'investissement architectural de toute la séquence, et l'ordre n'est pas
négociable** : AUTH-3 (espaces de travail) et DROIT-1 (tiering) se posent tous les deux
DESSUS. Les écrire avant reviendrait à auditer 93 points d'entrée deux fois, puis trois.

Le risque n'est pas la difficulté, c'est l'exhaustivité. Une ACL qui couvre 109 routes sur
110 ne cloisonne rien — et le trou ne se voit pas, puisque tout marche. D'où la troisième
case, qui est la seule vraie protection : un test qui refuse une route non scopée.

Deux pièges propres à ce dépôt. La table FTS `recherche` **agrège OCR, note, tags et
lemmes** sans porter la moindre trace de collection : la scoper suppose de rejoindre le
résultat vers `regions → planches → albums → collection_album`, à chaque requête. Et
`main.py` fait 2 897 lignes : c'est là qu'ARCH-1 cesse d'être une coquetterie — poser un
point de passage propre dans un fichier de cette taille est exactement la décision que la
veille à seuil attendait.
