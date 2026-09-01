---
chantier: SANTE-1
statut: livré
---

# SANTE-1 — /api/sante annonce vivants des moteurs morts

**Arrêté sur** — 2026-09-01, `88ec031` : passe de revue APRÈS le push de `4cbd905`
(panneau **🩺 Moteurs**, règle pure dans `static/lib/sante.js`, section « Un moteur en
panne »). Elle a trouvé un cul-de-sac au clavier. Le chantier est LIVRÉ.

## Reste

### Le défaut
- [x] Un contrôle PROFOND existe à côté du rapide : `sante.profond()` importe réellement le moteur au lieu de le localiser
- [x] `/api/sante?profond=1` reflète le fait qu'un moteur **s'importe** ; la route sans paramètre garde son contrat historique, et un test vérifie qu'elle ne déclenche AUCUN import
- [x] Le coût reste tenable : voie profonde SÉPARÉE et mémoïsée par moteur — torch n'est chargé qu'une fois par process

### Ce qui doit être attrapé
- [x] Une pile où `import ultralytics` lève `torchvision::nms` est rapportée EN PANNE — build rejeté, `PANNE bulles, ocr`
- [x] Un Kumiko cassé par OpenCV 5 est rapporté en panne : Kumiko étant un SCRIPT et non une bibliothèque, on vérifie son point d'entrée ET la majeure d'OpenCV — build rejeté, `PANNE kumiko`
- [x] La cause est lisible : `{ok, erreur}` porte le type et le message de l'exception, borné à 300 caractères
- [x] Le moteur ABSENT est attrapé, ce que la suite ne sait pas faire : contrat d'image `tools/verifier_moteurs.py --exiger`, lancé au build — image sans modèle spaCy rejetée, `PANNE nlp`

### L'exposer à l'opérateur

- [x] L'UI expose l'état profond : bouton **🩺 Moteurs** dans la Bibliothèque → modale (`dialog.js`), bouton **Éprouver** ; un navigateur vérifie qu'OUVRIR le panneau n'appelle PAS `?profond=1`
- [x] Le panneau ne rejoue pas le mensonge : le contrôle rapide n'autorise que « présent, non éprouvé » — « opérationnel » exige un import réel. Table de vérité sous Node, deux mutations éprouvées
- [x] « Absent » et « en panne » ne se confondent pas : un moteur non installé se dit non installé, même une fois éprouvé. Trois postes sur quatre n'ont aucun moteur ; y crier au rouge apprendrait à ignorer le panneau
- [x] Le bilan d'une épreuve distingue « rien à rapporter » de « rien rapporté » : un rapport profond vide ou parlant d'autres moteurs ne se lit plus « aucun moteur installé »
- [x] Le rouge du bilan se VOIT : `#sante-msg.erreur` n'était reçu par aucune règle CSS, le test compare les couleurs RENDUES
- [x] Les quatre états passent l'audit axe en thèmes sombre ET clair, le décor les forçant tous à l'écran ; l'accent rouge brut y échoue (mesuré)
- [x] Le panneau reste utilisable AU CLAVIER pendant une épreuve : `aria-disabled` et non `disabled`, parce que désarmer le bouton qui porte le focus le rend au `<body>` — Tab s'échappe et Échap ne ferme plus, quinze secondes durant. L'audit axe n'y voyait rien : il photographie un écran, il n'appuie sur aucune touche
- [x] Rouvrir le panneau pendant une épreuve n'efface pas le message qui explique le bouton grisé
- [x] `docs/deploiement-docker.md` § 8 « Un moteur en panne » : où le voir (panneau / route / CLI), les trois pannes rencontrées avec leur remède, et le redémarrage qu'exige la mémoïsation. Un test exige que chaque symptôme documenté ait son geste

## Contexte

**Trois mensonges le même jour**, tous découverts en construisant l'image de déploiement :

1. spaCy absent de l'image — `lemmes` aurait dit `false`, donc celui-là était honnête ;
   mais rien ne signalait que la table `tokens` resterait vide.
2. `torchvision` incompatible avec le torch CPU — `bulles: true` annoncé sur une pile où
   le premier `import ultralytics` levait une exception.
3. OpenCV 5 écrasant OpenCV 4 — `kumiko: true` annoncé alors que la passe 1 renvoyait 500.

Dans les trois cas, `find_spec` a trouvé un module et en a conclu qu'il fonctionnait.

**Le raccourci est défendable en mono-poste** : le chercheur est devant sa machine, il
clique, il voit l'erreur, il comprend. C'est le DÉPLOIEMENT qui le rend nuisible — la
route de santé devient l'unique fenêtre sur l'état des moteurs, pour quelqu'un qui n'a
plus d'accès shell, et elle affiche vert sur une machine en panne. Un vert qui ne mesure
rien est pire que pas de contrôle.

Ne pas surcorriger : importer les trois moteurs à chaque appel rendrait `/api/sante`
inutilisable (plusieurs secondes, et le chargement de torch en mémoire). C'est l'objet de
la troisième case — le contrôle profond doit être distinct du contrôle rapide.

Lié à INFRA-1 : c'est le déploiement qui transforme ce raccourci en angle mort.

## Ce que la passe d'après-coup a appris

Le défaut le plus sérieux du chantier a été trouvé APRÈS le push, en écrivant un test
pour autre chose : un état TRANSITOIRE — les quinze secondes d'une épreuve — pendant
lequel la modale cessait d'être une modale. Deux gardes le laissaient passer sans mentir,
chacune dans son droit : l'audit axe photographie un écran et n'appuie sur aucune touche ;
la suite ne traversait jamais cet état, faute d'un décor assez lent. Ce qui l'a rendu
visible n'est pas une relecture, c'est d'avoir eu besoin d'y passer.

Corollaire pour les prochains panneaux : un bouton qu'on désarme pendant son propre appel
est le patron par défaut, et il est faux dès que ce bouton porte le focus dans une modale.

## Ce qui a été décidé en fermant (2026-09-01)

**Le contrôle profond reste ouvert à tous**, et la route ne sort pas de
`HORS_PERIMETRE`. Le réserver aux administrateurs était défendable — le rapport cite des
chemins serveur, charger torch est un acte d'exploitation — mais le coût est BORNÉ (la
mémoïsation fait au plus quatre imports par processus), le rapport ne porte aucune donnée
de corpus, et la personne qui voit ses lots échouer est celle qui a besoin d'en lire la
cause. Fermer ici aurait été l'erreur d'AUTH-4 : gardé par défaut, pas par décision.

**Pas de bouton « revérifier » qui vide la mémoïsation.** Il aurait résolu un cas réel —
réparer à chaud dans le conteneur, puis re-cliquer et voir le vieux verdict — mais au prix
exact de ce qui justifiait de laisser la route ouverte : le coût cesse d'être borné dès
qu'on peut forcer les imports autant de fois qu'on insiste. Le chemin normal
(`docker compose up -d --build`) redémarre le processus et repose la question tout seul ;
le cas restant est DOCUMENTÉ, avec le `restart app` qu'il demande.

**Écarté sciemment, et ce n'est pas ce chantier** : une passe dont le moteur est ABSENT
reste cochable dans le lanceur de lots — on coche « Bulles », on lance, chaque planche
échoue en 503. Le contrôle rapide suffirait à le prévenir (l'absence est la seule chose
qu'il sache dire honnêtement). C'est un défaut voisin du lanceur, pas du diagnostic ; il
n'a pas de fiche parce qu'il tient en une case le jour où l'on touche à cette barre.
