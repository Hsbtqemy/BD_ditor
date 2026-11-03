# UX-20 : la miniature et la couverture, cadrage

Rédigé le 2026-11-02, soumis à Hugo avant tout code. Répond aux deux premières cases de
« Ce que le serveur doit dire, avant l'écran » de `pilotage/UX-20.md`.

## La réponse : aucune migration

Ni colonne ni table. **La v39 reste libre pour `docs/plusieurs-locuteurs-cadrage.md`.** Le
déploiement ne change pas la base ; il demande un seul geste, un outil lancé une fois (cf.
« L'existant »).

## La miniature

**Un fichier à côté du dérivé, nommé d'après lui** :
`derivatives/album_2/planche_0001.jpg` → `derivatives/album_2/planche_0001.miniature.jpg`.
Une seule fonction le dérive, `ingest.chemin_de_miniature(chemin_web)`. Tirée du dérivé,
320 px de large, JPEG qualité 75. Le code seul connaît ce nom.

Pourquoi pas de colonne : la miniature est une fonction pure de `chemin_web`. Une colonne
répéterait ce fait, devrait se déclarer retenue dans les sorties (`planches` est sous cliquet)
et demanderait une migration, pour ne rien apprendre de plus.

### Ce qui a été mesuré

Sur les 129 dérivés du poste, de 661 à 937 px de large, donc d'avant le plancher de 1 600 px :

| Forme | Médiane | Maximum | Fabrication |
|---|---|---|---|
| dérivé actuel (servi tel quel) | 151 Ko | 311 Ko | |
| 240 px, q75 | 13,9 Ko | 20,2 Ko | 6 ms |
| **320 px, q75** | **23,7 Ko** | **35,0 Ko** | **14 ms** |
| 480 px, q75 | 50,3 Ko | 77,6 Ko | 18 ms |

Une carte fait 10rem : 160 px, 320 px sur un écran à double densité. D'où 320. Deux cents
albums pèsent environ 4,7 Mo, et 500 planches environ 12 Mo sur le disque. **Non mesuré** : un
dérivé de 1 600 px, dont la miniature peut peser un peu plus.

### Écarté : la fabriquer à la volée

Sans fichier, il n'y aurait ni outil ni site d'effacement à toucher. Mais chaque image coûterait
au moins 14 ms de processeur, à la première ouverture de chaque navigateur, sur l'écran
d'ouverture de la Bibliothèque, avec un seul processus uvicorn et des passes ML à côté. Un
fichier se sert sans décoder.

### Le service

`GET /api/planches/{id}/miniature`, par l'accesseur gardé `_get_planche` : 404 hors de portée.
**Aucun chemin ne sort** : l'adresse porte l'identifiant de la planche. Le fichier n'est pas
dans l'allowlist de `/derivatives`, qui répond donc 404 sur ce nom : à tester. Même contrat de
cache que `/derivatives` (`no-cache`, ETag, 304 après le contrôle de portée), le code du 304
étant mis en commun. La grille charge en `loading="lazy"`.

Un cache plus long épargnerait des revalidations, mais laisserait voir une miniature après un
retrait d'accès : le cloisonnement l'emporte. À regarder sur l'écran codé.

Fichier absent : 404, et l'écran montre le titre sur un aplat, comme pour un album sans planche.

`tests/test_droit_export.py` ne la voit pas comme une porte (aucune de ses marques). Elle sert
une image à qui lit déjà la planche : DROIT-1 ne borde rien à l'intérieur de l'instance.

### Les copies sœurs et l'effacement

Deux sœurs ont le même `chemin_web`, donc la même miniature : `creer_copie` n'a rien à faire.
La règle tient en une phrase : **la miniature suit son dérivé.**

- `remove_planche_files` efface la miniature du dérivé qu'elle efface. Cela couvre aussi les
  fichiers « ailleurs » de `_effacer_les_images_d_une_copie` et le ménage de l'import ShareDocs.
- **`remove_album_files` est le piège.** `garder` y nomme les fichiers à laisser, tout le reste
  du dossier part. Sans correction, détruire une copie effacerait la miniature d'une image que
  sa sœur emploie encore. `garder` s'étend donc à la miniature de chaque chemin gardé. Un test
  et un mutant le vérifient.
- `ingest_image` écrit la miniature dans la fenêtre du numéro réservé, et la retire sur un
  échec.
- `tools/regenerer_derives.py` la refait avec le dérivé, sinon un dérivé corrigé garderait une
  miniature blanche.
- `orphelins()` de `tools/convertir_en_copies_de_travail.py` ne liste plus la miniature d'un
  dérivé désigné, et liste celle d'un dérivé disparu.

Une miniature oubliée à l'effacement ne se sert plus, aucune planche ne la désignant, mais elle
reste sur le disque jusqu'à ce que `orphelins()` la signale.

## L'existant

Un outil neuf, `tools/faire_miniatures.py`. **À blanc par défaut** : il dit combien manquent et
le poids ajouté, mesuré en les encodant ; `--appliquer` écrit. Il ouvre la base en lecture
seule, comme `regenerer_derives.py`, passe une seule fois par `chemin_web` (les sœurs partagent,
le jeu des bacs à sable compris) et ne refait pas ce qui existe. Il se lance en production sur
le mot de Hugo. Avant son passage, la grille montre des aplats, et rien n'est cassé.

## La couverture

Un champ de plus dans `GET /api/albums`, écrit une fois (`database.sql_couverture_d_album`), lu
dans la requête existante et donc sans une requête par album :

```sql
(SELECT p.id FROM planches p WHERE p.album_id = a.id
  ORDER BY p.role = 'recit', p.numero, p.id LIMIT 1) AS couverture
```

`couverture` est l'identifiant d'une planche, ou `null` pour un album sans planche. Le paratexte
se lit `role <> 'recit'`, parce que `config.py` déclare ce vocabulaire extensible. Les quatre
cas de la fiche se testent sur le JSON : paratexte, sans paratexte, plusieurs paratextes, aucune
planche. Un album de la liste est lu, donc sa couverture l'est : aucune borne de plus.

**Une conséquence de la règle tranchée** : un album dont seule la quatrième de couverture est
marquée paratexte aura sa quatrième de couverture en couverture, et une publicité finale de même.
C'est la règle, sans geste pour la corriger, et je n'y touche pas. La case « La densité se
regarde sur un corpus réel » est l'endroit pour le voir.

## Ordre des commits

1. `UX-20` : la miniature (écriture, effacement, route, outil, tests).
2. `UX-20` : la couverture dans `GET /api/albums`.

La documentation d'exploitation suit, pour l'outil (`docs/exploitation.md`).

Livré le 2026-11-03 en UN seul commit (`ba60449`), avec ce que `GET /api/albums` dit d'une
copie (`copie_de`, `a_moi`, `copie_par`) : les deux parties touchaient la même route et les
mêmes tests, et les séparer n'aurait rien rendu lisible.
