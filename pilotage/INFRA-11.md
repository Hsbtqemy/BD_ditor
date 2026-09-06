---
chantier: INFRA-11
statut: à venir
---

# INFRA-11 — le fichier des comptes a deux gardes, aucune ne lit ce qu'il contient

**Point de départ** — 2026-09-06 à 22:43, par une panne réelle. Ajouter un compte de test
a coupé le portail **six minutes**, pour tout le monde. Le hachage collé portait le préfixe
`Digest: ` que rend `authelia crypto hash generate` ; Authelia a refusé de démarrer et a
bouclé, une tentative par minute.

**Les deux gardes existantes ont laissé passer, et chacune pour une raison différente.**
`validate-config` ne lit pas ce fichier — mesuré le 2026-09-06 en y glissant une tabulation
illégale : « successfully », code 0. Le contrôle `yaml.safe_load` qu'INFRA-8 a ajouté
précisément pour combler ce trou a répondu **« YAML valide »** sur le fichier qui empêchait
le démarrage : il l'était. La syntaxe était parfaite, c'est la VALEUR d'un champ qui ne
l'était pas. Deux gardes, deux angles morts adjacents, et le seul contrôle qui voie
réellement est celui d'Authelia au démarrage — c'est-à-dire quand tout le monde est déjà
dehors.

## Reste

### Le contrôle qui manque
- [ ] Un contrôle REFUSE un condensé malformé et ACCEPTE un fichier correct, éprouvé dans
      les DEUX sens le même jour — une garde qu'on n'a vue que réussir ne prouve rien,
      c'est ce que `validate-config` puis `yaml.safe_load` ont fait croire chacune à leur
      tour
- [ ] Il attrape le cas EXACT du 2026-09-06 : un `password:` portant le préfixe `Digest: `
      rendu par `authelia crypto hash generate`, rejoué tel quel
- [ ] Il tourne SANS toucher à l'instance qui sert : ni redémarrage, ni conteneur qui
      prenne le port 9091, ni écriture dans `db.sqlite3`
- [ ] Il vérifie TOUS les comptes du fichier, pas seulement celui qu'on vient d'ajouter —
      c'est la même faute que le semis d'AUTH-5, une garde qui ne regarde qu'un endroit

### Que le geste soit franchissable seul
- [ ] `docs/exploitation.md` décrit la séquence complète — copie de sauvegarde, hachage
      sans son préfixe, contrôle YAML, contrôle du contenu, redémarrage, attente du
      `healthy` — et quelqu'un qui la suit sans rien savoir d'autre ajoute un compte sans
      couper le portail
- [ ] Le retour arrière est nommé au même endroit et vérifié : la copie `.avant` a servi
      le 2026-09-06 et c'est elle qui a rétabli le service

### Ce que la panne a laissé traîner
- [ ] Les copies `.avant` ne restent pas dans `deploy/authelia/` : elles portent des hashs,
      `.gitignore` ne les attrape pas (motifs par nom EXACT, vérifié le 2026-09-06), et
      trois fichiers de cette famille ont déjà bloqué un déploiement le soir même

## Contexte

**La forme du défaut est celle qu'on répète.** `validate-config` donnait une assurance sur
un fichier qu'il ne lisait pas ; `yaml.safe_load` en donne une sur une propriété qui n'est
pas celle qui casse. Aucune des deux n'a échoué : elles ont **approuvé sans regarder ce
qu'il fallait**. C'est le mode d'échec d'ARCH-2 — une garde qui reste verte en ne voyant
plus — et le troisième exemplaire de la journée du 2026-09-06, après l'inventaire de routes
et la garde géométrique du bandeau.

**Ce qui rend celui-ci plus cher que les autres** : les deux précédents rendaient un vert
en salle de mesure. Celui-ci a coupé la production. Entre un fichier qu'aucun test ne
couvre et un service dont le démarrage EST le seul contrôle, il n'y a plus de filet.

**Deux pistes, à trancher en les essayant.** `authelia crypto hash validate` sait dire si
un condensé est bien formé, mais il faut vérifier qu'il ne demande pas le mot de passe en
clair — auquel cas il ne sert pas ici. Sinon, un examen des valeurs `password:` en Python
(préfixe `$argon2id$`, nombre de champs séparés par `$`, paramètres présents) suffit
largement et n'ajoute aucune dépendance, PyYAML étant déjà là. La première dit la vérité
d'Authelia, la seconde ne dépend de rien : mesurer avant de choisir.

**Ce chantier ne cherche pas à valider le fichier « en général ».** Il vise ce qui a coupé
le service, et ce qui le coupera encore : un champ que seule Authelia sait lire. Un
validateur exhaustif serait une deuxième implémentation de son analyseur, donc une
troisième garde à faux — exactement ce qu'on répare.

**Voisinage.** INFRA-8 (le parcours d'un compte neuf, et les deux gardes dont celle-ci
montre les limites), INFRA-9 (Authelia relit sa configuration au démarrage du processus —
d'où le redémarrage qui expose le défaut), INFRA-10 (le timer : un déploiement automatique
qui redémarrerait Authelia rendrait cette panne silencieuse et périodique).
