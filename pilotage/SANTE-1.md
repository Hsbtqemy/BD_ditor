---
chantier: SANTE-1
statut: à venir
---

# SANTE-1 — /api/sante annonce vivants des moteurs morts

**Point de départ** — trois fois en une journée, le 2026-08-27, la route a répondu
`true` pour un moteur inutilisable. Aucune ligne écrite pour y remédier.

## Reste

### Le défaut
- [ ] `bulles_available()` et `ocr_available()` cessent de conclure d'un `importlib.util.find_spec` : il LOCALISE un module, il ne l'importe pas, et ne peut donc voir aucune incompatibilité binaire
- [ ] La disponibilité annoncée par `/api/sante` reflète le fait qu'un moteur **s'importe**, pas qu'un fichier existe sur le disque
- [ ] Le coût reste tenable : importer torch prend plusieurs secondes, la route rapide ne doit pas devenir lente — soit un contrôle approfondi séparé (`?profond=1`), soit un résultat mis en cache au premier appel

### Ce qui doit être attrapé
- [ ] Une pile où `import ultralytics` lève `RuntimeError: operator torchvision::nms does not exist` est rapportée EN PANNE, pas disponible
- [ ] Un Kumiko présent mais cassé par une version d'OpenCV incompatible est rapporté en panne — aujourd'hui `kumiko_available()` vérifie le clone et `cv2`, sans jamais exécuter Kumiko
- [ ] La cause de l'indisponibilité est lisible dans la réponse : un opérateur à distance doit pouvoir diagnostiquer sans accès shell

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
