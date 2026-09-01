---
chantier: AUDIT-1
statut: interrompu
audit: AUDIT.md
---

# AUDIT-1 — les reliquats ouverts des cinq passes d'audit

**Arrêté sur** — le commit `1786a17`, 2026-08-31 : B6 avait un JUMEAU dans la visionneuse,
trouvé par une seconde passe de revue sur un commit déjà fait. `viewer.js` posait
`state.planche.statut = "segmentee"` après un clic sur « Segmenter », exactement comme la
réponse d'import. La première passe avait relevé les quatre sites d'écriture EN BASE et
s'était arrêtée à la frontière HTTP, alors que le client tient sa propre copie de l'état.

**Et il aura fallu deux corrections pour dire vrai de cette seule ligne**, ce qui vaut
mieux d'être noté que le correctif lui-même. J'ai d'abord écrit le cas NON TESTABLE, « faute
de Kumiko dans le serveur live » — faux, `lib/kumiko` est cloné et le serveur live segmente
pour de bon ; je ne l'avais pas regardé. Puis j'ai écrit que l'écran affichait la
régression — faux aussi, et c'est le test qui l'a dit en passant AVEC la constante en dur.
Le défaut est réel mais DIFFÉRÉ : `segmenter()` ne redessine pas le bandeau, tandis que
`selectPlanche()` lit `state.planches` EN MÉMOIRE sans refetch, `state.planche` en étant le
même objet — la valeur faussée ressort au premier réaffichage, une re-sélection suffit.
D'où le clic dans le test, sans lequel il est vacant. **« Non testable » est une
CONCLUSION, et une conclusion se vérifie comme le reste.**

Avant lui, le commit `cff09fc` : la zone **Transitions de statut** est close
à son tour. Une seule zone reste, les latents de segmentation.

Le relevé a valu mieux que les deux pointeurs de la fiche : `statut` s'écrit à QUATRE
endroits et **rien ne branche dessus** — aucune route ne le teste, aucun job ne le filtre.
Son unique lecteur est la barre d'avancement du corpus. C'est un marqueur déclaratif, pas
une machine à états, et cela change ce qu'il fallait corriger : un seul `UPDATE` mêlait un
FAIT (`date_segmentation`, vrai à chaque passage) et une PRÉTENTION (`statut`, où en est le
travail humain). Les écrire ensemble était tout le défaut.

Avant lui, le commit `8195037`, 2026-08-31 : la zone **Tests faibles** est close, les
deux autres sont intactes. Les quatre corrections ont une parenté qu'on ne voit qu'en les
faisant ensemble — aucune ne réparait un bug, toutes réparaient une AFFIRMATION. Un test
qui accepte deux contrats opposés, un qui reconnaît une page à trois lettres, un qui
accepte un octet, un qui audite un écran sans vérifier l'avoir rempli : dans les quatre
cas le code était juste et le filet troué.

**Ce qui a coûté le plus n'était pas la correction mais la MESURE.** Pour T4a, la première
mesure tournait sur une base non initialisée où TOUT répondait 400, requête valide
comprise — la conclusion « les requêtes spéciales sont refusées » était fausse, et
seul le détail du message (`no such table: regions`) l'a dit. Pour T8, le diagnostic écrit
d'abord était faux lui aussi : le marqueur `live_server(True)` était bien là, contrairement
à ce que j'avais conclu.

**Point de départ** — les cinq passes d'audit de juin 2026 ont été largement traitées ;
sept constats sont restés ouverts, dispersés dans les sections « restent ouverts » et
cités nulle part ailleurs que dans `AUDIT.md`.

## Reste

### Transitions de statut
- [x] **B6 (régression) — la machine n'efface plus l'avancement déclaré** (`database.avancer_statut`, appelé par `segment_planche`). Le `UPDATE` unique est scindé : la date est posée à chaque passage — c'est un fait —, le statut ne peut qu'avancer. L'ordre vient de `STATUTS` et de nulle part ailleurs, un `CASE WHEN` en SQL le recopierait. Trois tests, dont le PENDANT sans lequel le premier ne prouverait rien : un correctif qui n'écrirait plus jamais le statut passerait la non-régression avec brio. `run_kumiko` y est simulé, pour que la garde tourne aussi là où Kumiko n'est pas installé — c'est-à-dire en intégration
- [x] ~~B6 (ordre) — la route `PATCH /api/planches/{id}/statut` valide un ORDRE de transition~~ — **ÉCARTÉ le 2026-08-31**, et c'est la conséquence directe de la doctrine retenue : *la machine ne recule jamais, l'humain le peut*. Si le retour humain est légitime, il n'y a plus d'ordre à valider. Deux faits relevés dans le code appuient l'arbitrage, et aucun n'était connu avant de le chercher. **La route n'a AUCUN appelant dans l'interface** — `corpus.js` affiche la pastille et ne l'écrit jamais —, si bien que « l'humain peut reculer » reste aujourd'hui théorique. Et son seul appelant réel, `tools/semer_demo.py`, pose `annotee` sur une planche fraîchement importée : un saut de deux crans, que toute validation d'ordre strict casserait. La décision est écrite dans `update_statut`, à côté du contrôle d'appartenance qui subsiste

### Tests faibles
- [x] **T2 — renommé, et ce qu'il ne teste pas est écrit dedans** (`tests/test_live_coherence.py`). Le test était JUSTE : un client séquentiel est la bonne forme pour le bug qu'il garde — un commit émis après la réponse se révèle en relisant tout de suite, pas en écrivant à plusieurs. C'est son NOM qui mentait. Plutôt que de seulement renommer, la docstring nomme désormais la concurrence qui reste non testée — ni deux jobs sur `_run_lock`, ni worker ↔ serveur, ni `make_backup` pendant une écriture — parce qu'un nom qui survend ne se remplace pas par un silence. Quatre documents mis à jour, et le lien mort du constat d'audit retiré (il pointait des lignes 83-92 d'un fichier qui n'en comptait que 45)
- [x] **T4 — les trois assertions molles sont resserrées, et la mesure a été le vrai travail.** (a) `status_code in (200, 400)` acceptait deux contrats OPPOSÉS sur une seule entrée, donc n'en vérifiait aucun : mesuré, la route répond 200 avec zéro résultat sur douze syntaxes FTS invalides — un choix défendable qui n'était écrit nulle part. Le test le fixe ET vérifie d'abord qu'une requête valide trouve sa cible, sans quoi « zéro partout » passerait sur une recherche morte. (b) `"BD" in r.text` reconnaissait n'importe quelle page parlant de bande dessinée : le shell se reconnaît maintenant à son titre, sa langue et ses scripts — `viewer.js` étant ce qui le distingue des trois autres surfaces. (c) `len(data) > 0` passait sur un octet : le zip doit s'ouvrir et porter la base, ce que `_open_snapshot` disait déjà à deux lignes de là
- [x] **T8 — le décor était bon, mais rien ne le contrôlait**, et mon premier diagnostic était faux : j'avais conclu que le marqueur `live_server(True)` manquait ; il était là. Le vrai défaut est plus discret — le test n'affirmait RIEN de son propre montage, si bien que n'importe quelle régression d'authentification, de route ou de contrat de token aurait vidé la modale sans le faire échouer, axe trouvant une modale vide parfaitement accessible. Trois gardes : la divergence est confirmée côté serveur, les deux auteurs sont NOMMÉS, et l'écran doit montrer la `.accord-table` — que le rendu ne produit que si `retouches` est non nul. L'absence de tokens devient un skip EXPLICITE : ne rien pouvoir mesurer et mesurer zéro ne sont pas le même résultat
- [x] **T4 (suite) — l'horodatage est vérifié comme tel** : motif `bd_annotator_AAAAMMJJ_HHMMSS.zip`, et la date doit tomber DANS l'intervalle d'exécution du test. Le contrôle de format seul laisserait passer une constante figée — or c'est précisément l'horodatage qui empêche une sauvegarde d'écraser la précédente

### Latents de segmentation
- [ ] S1/S5 — dans `segment_planche`, le détachement (`pipeline/segmentation.py:254`, un seul niveau) et la désindexation FTS (`:293`, les seules cases supprimées) deviennent récursifs, sur le modèle du `WITH RECURSIVE` de la route `delete_region` (`main.py:782`) et de `pipeline/bulles.py:139`
- [ ] S6 — re-segmenter deux fois de suite une planche à case annotée conservée donne le même résultat la seconde fois qu'à la première (point fixe)
- [ ] O1 — le regroupement en rangées de `pipeline/ordering.py:37-46` ne peut plus agglomérer transitivement des cases en escalier sur `y` : la boucle élargit `row["top"]` par `min()` à chaque ajout, donc de proche en proche

## Contexte

Fiche d'agrégation volontaire : sept constats mineurs ou latents qui ne justifient pas
sept fiches, mais qui n'existaient plus pour qui planifie — ils ne vivaient que dans
`AUDIT.md`, exactement le défaut que le contrôleur du journal cherche.

**S1/S5 est le seul à surveiller** : il est marqué « latent » parce que la profondeur
d'arbre est aujourd'hui ≤ 2, ce qui le neutralise. Ce n'est pas une correction, c'est une
coïncidence de données — le jour où une 3ᵉ profondeur est autorisée, il devient une perte
de données silencieuse. À traiter AVANT toute évolution de la hiérarchie des régions.

**Deux trouvailles hors constat, l'une et l'autre nées du relevé.** `main.py` recopiait
`planche["statut"] = "segmentee"` dans la réponse d'import : la ligne aurait MENTI dès que la
segmentation cesse de reculer le statut, en annonçant un recul qui n'a pas eu lieu — elle
rend l'effectif. Et le `except Exception: pass` de cette même boucle a AVALÉ, le jour même,
un `TypeError` introduit par ce commit : la seule trace était un statut resté `importee`,
c'est-à-dire un symptôme qu'on attribue à la segmentation et jamais à un bug. Le
best-effort est légitime — un import réussi ne doit pas être perdu pour une segmentation
ratée — mais se taire ne l'est pas, et c'est la même faute que le lot qui s'annonçait
terminé (CONC-2). Il dit désormais ce qu'il avale.

**Les pointeurs ont re-pourri en cinq jours, et de ma propre main.** Au 2026-08-31, cinq
des dix références de cette fiche étaient mortes : les quatre `main.py` (décalées par le
bloc CSP de SEC-2 et les ajouts d'AUTH-1) et celle de T8 (`test_e2e_a11y.py:372`, devenue
398 par les tests que j'y avais ajoutés le matin même). Les constats, eux, étaient tous
encore exacts — comme le 27 août. C'est la démonstration la plus nette qu'on puisse
souhaiter : ce qui pourrit dans une fiche n'est pas le raisonnement, c'est l'adresse.
Cf. la note de mémoire sur les fiches périmées.

Les références de ligne ci-dessus ont été **revérifiées contre le code le 2026-08-27** :
celles de `AUDIT.md` avaient dérivé (B6 y pointe `main.py:631-642`, où il n'y a plus de
`statut` ; T2 y pointe des lignes 83-92 d'un fichier qui n'en compte que 45 ; T4 y pointe
`test_api.py:208/245`, devenus de vraies assertions). Les constats eux-mêmes sont tous
encore vrais — seuls les pointeurs étaient périmés.

`audit: AUDIT.md` est déclaré ici pour que l'écran renvoie à la source. Attention :
`AUDIT.md` n'a pas de tableau de constats à codes `X-NN`, ses codes sont de la forme `B6`,
`T2`, `S1`. Le contrôleur le rangera donc « INCONNU » plutôt que d'en compter les
constats ouverts — c'est le document qu'il faudrait reformater, pas la règle de lecture.
