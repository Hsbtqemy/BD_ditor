---
chantier: SHARE-2
statut: à venir
---

# SHARE-2 — ShareDocs ne doit pas vivre dans le seul Atelier

**Point de départ** — ouvert le 2026-09-08 en marge d'EXP-1, sur une remarque d'usage :
*« il vaudrait mieux une redirection ou l'intégration du module pour se connecter plutôt
que dire où trouver le chemin »*. Le premier des deux est fait le jour même.

**Le périmètre a doublé une heure plus tard, et la seconde moitié est la plus demandée.**
Un dépôt d'essai a échoué sur un `404` parce que le chemin saisi était le FIL D'ARIANE de
l'interface web de ShareDocs — guillemets, chevrons, et « Mes fichiers » là où le WebDAV
dit `@Home`. Le champ demandait de TAPER un chemin que l'explorateur de l'Atelier donne en
trois clics. Ce n'est pas un défaut de message : c'est un composant qui manque là où on en
a besoin, exactement comme la session.

## Reste

- [ ] Le formulaire de connexion ShareDocs (URL, utilisateur, mot de passe, sélecteur de compte) vit dans un module montable, chargé par au moins deux surfaces
- [ ] L'Administration ouvre la session SANS quitter la page — plus d'aller-retour vers l'Atelier pour un formulaire de trois champs
- [ ] **L'explorateur de dossiers sert à CHOISIR la destination d'un dépôt**, au lieu de taper un chemin. Attendu : depuis la ligne de dépôt, on parcourt son espace et on désigne un dossier — le champ se remplit tout seul, avec le chemin RÉEL et non le nom d'affichage
- [ ] L'import d'images depuis ShareDocs continue de fonctionner à l'identique : la coupe sépare la SESSION et l'EXPLORATEUR de l'IMPORT, qui reste propre à l'Atelier
- [ ] Le composant refuse de désigner un dossier en lecture seule, ou le signale — `upload` rend déjà un 403 nommé sur ce cas (montages « tools »), et le découvrir après avoir tout préparé est le pire moment
- [ ] Le sélecteur de compte (`perso` / `instance`) gouverne les deux surfaces depuis un seul endroit, sans qu'une page puisse en afficher un que l'autre ignore
- [ ] Un test Node éprouve la logique extraite par table de vérité — la résolution « la mienne si j'en ai une, celle de l'instance sinon », et le refus nommé sur un compte absent (SHARE-1)

## Contexte

**Ce qui est DÉJÀ fait, et qu'il ne faut pas refaire.** EXP-1 a posé l'aller-retour : le
panneau de dépôt lit `GET /api/sharedocs/etat`, et quand aucune session n'est ouverte il
affiche un lien vers `/?sharedocs=1&retour=/administration`. L'Atelier sait désormais
ouvrir sa modale par lien profond, et `nav.js` ramène. Le bouton a cessé d'être un
cul-de-sac — il échouait auparavant sur une erreur de transport WebDAV, qui ne nomme pas
la cause.

`static/lib/depot.js` porte le lien plutôt que l'écran, et `tests/js/depot.test.js`
confronte sa valeur à la règle de `nav.js`. Ce n'est pas de la précaution : `safeRetour`
n'accepte qu'un chemin commençant par `/` — protection contre l'open-redirect — et un
`retour=administration` sans barre serait REJETÉ en silence, faisant disparaître le
bouton « ← Retour » sans la moindre erreur.

**Ce qui a été fait EN ATTENDANT, et qui ne remplace pas ce chantier.** Le message d'un
dossier absent nomme désormais sa cause : `pipeline/sharedocs.upload` distingue 404/409 —
le PUT WebDAV ne crée pas les dossiers manquants — et dit la forme attendue plutôt que de
rendre le code brut. Le champ porte un exemple (`@Home/mon-dossier`) et une phrase sur le
chemin relatif. C'est un pansement honnête : il apprend à taper juste, là où le chantier
supprimera la saisie.

**Pourquoi ça ne suffit pas.** Trois champs et un bouton ne justifient pas de quitter la
page où l'on travaille. Et l'aller-retour a un défaut propre : la session ShareDocs vit en
MÉMOIRE SERVEUR (SHARE-1, jamais sur disque), donc un redémarrage la perd — on refait
l'aller-retour, pour un formulaire.

**La coupe, et c'est là que le chantier est risqué.** `viewer.js` mêle trois choses sous
le même bouton : la SESSION (connexion, déconnexion, choix du compte), l'EXPLORATEUR de
fichiers WebDAV, et l'IMPORT d'images. Les DEUX premières doivent voyager — c'est
l'élargissement du 2026-09-08 —, la troisième reste ici : importer des planches est un
geste de la Bibliothèque, pas d'une page d'administration. Les séparer
sans casser l'import est tout le travail — l'explorateur lit la session résolue à chaque
appel, et le sélecteur de compte gouverne aujourd'hui le panneau entier.

**Où le module doit vivre.** `static/lib/`, à côté de `dialog.js` — le précédent qui
compte, puisqu'il manipule le DOM sans y toucher au chargement. Le critère d'entrée de ce
dossier est une PROPRIÉTÉ vérifiable, pas le partage : ce qui s'y range ici est la
résolution de compte de SHARE-1 (« la mienne si j'en ai une, celle de l'instance sinon ;
forcer un compte absent est une erreur nommée, jamais un repli silencieux »), qui est une
table de vérité et se teste comme telle.

**Ce que ce chantier ne touche pas.** `pipeline/sharedocs.py` ne sait rien du proxy et
range ce qu'on lui donne ; `main._principal_sharedocs` reste le seul endroit qui décide
qui est « je ». La coupe est côté écran seulement.
