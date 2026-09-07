---
chantier: SHARE-2
statut: à venir
---

# SHARE-2 — la session ShareDocs doit s'ouvrir là où on en a besoin

**Point de départ** — ouvert le 2026-09-08, en marge d'EXP-1, sur une remarque d'usage :
*« il vaudrait mieux une redirection ou l'intégration du module pour se connecter plutôt
que dire où trouver le chemin »*. Elle est juste, et le premier des deux est fait.

## Reste

- [ ] Le formulaire de connexion ShareDocs (URL, utilisateur, mot de passe, sélecteur de compte) vit dans un module montable, chargé par au moins deux surfaces
- [ ] L'Administration ouvre la session SANS quitter la page — plus d'aller-retour vers l'Atelier pour un formulaire de trois champs
- [ ] L'import d'images depuis ShareDocs continue de fonctionner à l'identique : la coupe sépare la SESSION de l'EXPLORATEUR de fichiers, qui reste dans l'Atelier
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

**Pourquoi ça ne suffit pas.** Trois champs et un bouton ne justifient pas de quitter la
page où l'on travaille. Et l'aller-retour a un défaut propre : la session ShareDocs vit en
MÉMOIRE SERVEUR (SHARE-1, jamais sur disque), donc un redémarrage la perd — on refait
l'aller-retour, pour un formulaire.

**La coupe, et c'est là que le chantier est risqué.** `viewer.js` mêle trois choses sous
le même bouton : la SESSION (connexion, déconnexion, choix du compte), l'EXPLORATEUR de
fichiers WebDAV, et l'IMPORT d'images. Seule la première a besoin de voyager. Les séparer
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
