---
passe: Compte collectif et Ctrl+Z borné
chantier: AUTH-6
duree: 20 min
derniere: 2026-09-11
---

# QA — un login partagé se déclare, et Ctrl+Z se borne à cinq minutes

**Où** — la pile de recette locale, `https://bd.127-0-0-1.sslip.io` (certificat de recette
à accepter une fois). Les mots de passe des comptes, `collectif` compris, sont dans
`C:\temp\bd-recette\comptes.txt`, hors dépôt.

**Libellés et chemins remis à l'écran du 2026-09-18 (`6ea6b60`), les cases N'ONT PAS été
retouchées.** Le bloc « 👤 Comptes vus » a disparu avec la vue qu'il habitait, remplacé par
« 👥 Comptes et groupes » et ses trois axes ; le sélecteur dit « une personne » / « un login
partagé » au lieu de « Nominatif » / « Collectif ». Les cases cochées l'ont donc été sur
l'ANCIEN écran : elles disent que le comportement a été vu, pas que ces libellés-ci l'ont
été. Une passe se remet à jour pour rester REJOUABLE — une case vraie mais inatteignable
coûte ce que coûte une case fausse —, et c'est pourquoi la mise à jour est datée plutôt que
silencieuse.

**Deux identités à la fois, pas trois.** Une session Authelia est partagée par tous les
onglets d'une fenêtre — et, dans Chrome, par TOUTES les fenêtres privées : en ouvrir une
seconde ne donne pas une identité de plus, elle prend celle de la première. On dispose donc
d'une fenêtre normale et d'une fenêtre privée. Ordre qui tient : `collectif` dans la fenêtre
normale pour toute la passe ; `proprio` dans la fenêtre privée pour le témoin ; puis fermer
TOUTES les fenêtres privées et en rouvrir une pour `admin-bd` — c'est ce qui efface la
session précédente.

**Ce que la passe éprouve.** Sous un login partagé, l'agent du journal ne désigne plus une
personne : sans borne, n'importe qui défait par Ctrl+Z l'acte d'un collègue. La borne ne
s'applique qu'à un compte DÉCLARÉ collectif, et c'est la déclaration qu'il faut voir
fonctionner. `collectif` écrit sur « Collection Test » par son groupe `etudiants`.

**Une seule attente de plus de cinq minutes**, si l'on suit l'ordre : deux régions posées
avant, et c'est la déclaration faite APRÈS l'attente qui change la réponse de Ctrl+Z. Poser
la région du témoin (dernière zone) au début de cette même attente évite d'en faire une
seconde.

**L'état de départ se vérifie, il ne se suppose pas.** Sous `admin-bd`, Administration →
👥 Comptes et groupes, axe *Comptes*, fiche de `collectif` : sa **Nature** doit être « une
personne », ou la fiche doit dire « Nature : se déclare à sa première connexion. » — le
sélecteur n'apparaît qu'après la première connexion du compte, et un compte reste nominatif
tant que personne ne l'a déclaré. Une partie précédente non remise en état le laisse « un
login partagé », et la troisième case échoue alors sans que l'écran y soit pour rien.

**Poser une région**, dans toute la passe : en mode **Édition** (touche `E`), **`Maj`
enfoncée**, tirer un rectangle sur la planche à la souris, bouton maintenu, puis relâcher —
la région apparaît, déjà sélectionnée. `Maj` n'est pas un détail : les planches
d'« esther v1 » sont couvertes de cases, et un tracé commencé dans l'une d'elles sans `Maj`
sélectionne la case au lieu de dessiner ; avec `Maj`, la région devient une bulle de cette
case, ce qui ne change rien à la passe. Un seul tracé, sans la redimensionner ni la déplacer
ensuite : chaque retouche est un enregistrement de plus, et Ctrl+Z défait le dernier
enregistrement, pas la région (constat d'`UX-5`).

**Ne plus cliquer sur une région déjà sélectionnée** — celle qu'on vient de tracer l'est
d'office. Relâcher le clic l'enregistre comme une modification, même si elle n'a pas bougé,
et c'est ce non-geste que Ctrl+Z déferait ensuite : la case d'après échouerait sans que la
borne y soit pour rien. Deux clics sur une case la feraient passer de « kumiko » à
« corrigé ». Et avant chaque Ctrl+Z, `Échap` : Ctrl+Z n'agit que hors d'un champ de saisie.

### Avant la déclaration
- [x] Sous `collectif` (mot de passe seul, sans second facteur), l'Atelier ouvre « esther v1 » et ses planches s'affichent
- [x] Sous `collectif`, deux régions tracées l'une après l'autre sur une même planche apparaissent chacune, et le panneau les dit « Source : manuel ». Noter le NUMÉRO de la première — ligne « Région » du panneau, « #N », lu juste après le tracé, sans cliquer — et l'HEURE de la seconde, à l'horloge de l'ordinateur : l'application n'en affiche aucune. Deux régions, parce que chaque Ctrl+Z en consomme une — le premier défait la seconde, la première reste pour éprouver la borne après la déclaration. Sur la même planche, pour voir laquelle disparaît
- [x] Plus de cinq minutes après la seconde, toujours sous `collectif`, `Échap` puis Ctrl+Z : la seconde région disparaît, et le message dit « Annulé : création d'une région ». Un compte non déclaré n'a aucune borne

### La déclaration
- [x] Sous `admin-bd` (second facteur TOTP ; le code d'enrôlement de la première fois est écrit dans `authelia/notification.txt` de la pile), Administration → 👥 Comptes et groupes, axe *Comptes* : `collectif` figure dans la liste, et sa fiche s'ouvre
- [x] Son sélecteur **Nature** passe de « une personne » à « un login partagé », la fiche répond « Nature enregistrée. », et le dépliant « Ce que change un login partagé » dit que Ctrl+Z n'y remonte que les cinq dernières minutes, et qu'aucun droit d'accès n'en dépend
- [x] Sous `collectif`, `Échap` puis Ctrl+Z ne défait PAS la première région, vieille de plus de cinq minutes, et un message neutre (pas une erreur rouge) dit « Rien à annuler dans les 5 dernières minutes : sur un compte partagé, Ctrl+Z ne remonte pas plus loin. »
- [x] Toujours sous `collectif`, une troisième région posée puis, aussitôt, `Échap` et Ctrl+Z : elle disparaît. La borne n'empêche pas l'annulation récente

### Témoin
- [x] Sous `proprio`, compte nominatif : une région posée, puis PLUS de cinq minutes sans autre geste sous `proprio`, puis `Échap` et Ctrl+Z — elle disparaît. C'est le délai qui fait le témoin : annulée aussitôt, elle disparaîtrait sous n'importe quel compte, et la case ne prouverait rien. Ce qui borne est la nature du compte, pas l'instance

### Remettre en état
- [x] La première région de `collectif` est toujours là — c'est exactement ce que la passe a vérifié. Sous `proprio`, en mode Édition, la sélectionner d'UN seul clic, sans `Maj` — un second l'enregistrerait comme modifiée — et vérifier dans le panneau que c'est bien ELLE — « Source : manuel », et « Région » au numéro noté à la pose — avant `Suppr` : la suppression part aussitôt, sans confirmation, et emporte les régions enfants. Le message dit « Région supprimée ». Une erreur de sélection se rattrape par Ctrl+Z sous `proprio` : la suppression est l'acte pour lequel l'annulation a été conçue
- [x] Sous `admin-bd`, `collectif` repasse en « Nominatif (une personne) » : sans cela, la prochaine partie échoue dès sa troisième case
