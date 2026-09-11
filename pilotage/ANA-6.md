---
chantier: ANA-6
statut: livré
---

# ANA-6 — détails de recherche laissés de côté par B2/B3

**Arrêté sur** — l'audit e2e de la concordance annotée déclare son périmètre ; commit
`3f605ab`, 11 septembre. Le rendu des tags et de la note (colonne de tags en aligné, tout
en liste), choisi sur maquette entre cinq mesures, est au commit `03ebf9e`.

## Reste

- [x] La recherche de lemme accepte un préfixe, par joker EXPLICITE : `otage*` trouve « otage » et « otages », `otage` ne trouve que « otage » — la règle s'écrit une fois (`_clause_lemme`, socle) et l'analyse comme la Recherche la lisent
- [x] Une ligne de concordance affiche les tags et la note de la région, sans second aller-retour serveur : tags propres puis hérités de la case (marqués « case »), filtrés par la portée des termes ; en aligné une colonne de tags (deux puces puis « +N ») et un repère 📝, en liste la note entière
- [x] La concordance a un export dédié, cohérent avec les autres exports (`_csv_safe` appliqué) — livré par ANA-7 (`381cf77`), qui l'avait absorbé et annonçait que la case se cocherait ici ; ANA-6 y ajoute les colonnes `tags` et `note`, et un nom de fichier qui ne plante plus sur « cœur »

## Contexte

**La raison d'être écrite de la première case était fausse.** Elle disait : « sans préfixe,
chercher “otage” ne trouve pas “otages” dès que le lemme n'est pas résolu, ce qui arrive
quand spaCy est absent ». Sans spaCy il n'y a PAS de tokens (`tokens_effectifs` part
`FROM tokens`) : la concordance est vide, préfixe ou non. Le besoin réel est ailleurs —
une lemmatisation ratée qui laisse un mot rare à sa forme fléchie, fréquent sur un
lettrage en capitales, ou une famille de mots qu'on veut balayer d'un coup.

**Le préfixe est explicite parce qu'un préfixe implicite mentirait en silence.** La
cellule d'un croisement ouvre sa concordance par la valeur EXACTE ; avec un préfixe
implicite, `pas` y aurait aussi compté « passer » et « passage », et la descente aurait
rendu plus que la cellule, avec des nombres plausibles. Le champ de la Recherche
s'annonçait « lemme exact » : il lit désormais le joker comme l'analyse, et son libellé le
dit — une descente de l'une vers l'autre ne change plus de sens en chemin.

**Le troisième arbitrage s'est tranché sur maquette, et la maquette a d'abord eu tort.**
Cinq mesures du rendu aligné, de « rien » à « tout », sur six occurrences d'exemple aux
couleurs réelles de l'app, dans les deux thèmes et à trois largeurs. La première version
proposait C (puces dans la colonne de la citation) et disait D (une colonne de tags à
part) « très réduite » à 560 px. C'était faux : les colonnes de méta sont en `auto`, la
colonne fusionnée de C est donc déjà aussi large que la citation la plus longue PLUS ses
puces, et D ne coûte qu'une gouttière de 12 px de plus. Relevé en répondant à la question
« D semble plus propre, non ? » — il l'était. Seul surcoût réel : une colonne vide quand
aucune ligne n'a de tag, d'où la règle qui ne la pose que lorsqu'une ligne affichée a
quelque chose à y mettre.

**Deux défauts trouvés en route, un corrigé, un signalé.**

- *Corrigé* (`1a1bc8a`) : l'export de la concordance PLANTAIT sur « cœur ». Le lemme saisi
  finissait tel quel dans `Content-Disposition`, qui s'encode en latin-1 ; « œ » n'y est
  pas, d'où un `UnicodeEncodeError` et un 500. Le joker `*` aurait mordu au commit
  suivant, Windows le refusant dans un nom de fichier.
- *Signalé, NON traité* : la Recherche montre à un lecteur le tag LOCAL d'une collection
  qu'il ne lit pas — mesuré dans le JSON de `/api/recherche` ET dans son export CSV, alors
  que `/api/tags` le lui masque. `_recherche_rows` joint les tags d'une région sans
  `clause_terme`. La concordance, elle, les filtre depuis `efeb0bf`. C'est une autre
  surface qu'ANA-6 : remonté à l'équipe pour qu'elle décide qui le prend.

**L'audit axe ne voyait pas les puces neuves, et un fichier à part les lui montre.** Le
décor de `test_e2e_a11y` sème une bulle à UN tag, sans case parente : ni puce héritée, ni
« +N » n'y sont jamais rendus. `tests/test_e2e_concordance_tags.py` sème une case taguée
et une bulle à trois tags, vérifie que ce qu'il audite est à l'écran AVANT de l'auditer,
dans les deux thèmes et les deux rendus, et mesure qu'à 560 px la page ne défile pas de
côté. Il a payé dès son premier lancement : la puce héritée se lisait « casecolère » —
deux `<span>` collés que seule une marge écartait à l'œil. axe ne le voit pas ; un test
qui lit le TEXTE, si. Et il avait lui-même oublié de déclarer son périmètre, ce que seule
la suite complète a dit — la passe navigateur ne collecte pas la garde des surfaces.

**Deux réglages retenus faute d'avis contraire** : le plafond de puces en aligné (deux) et
le repère de note (📝, le signe que la Recherche emploie déjà). Les changer ne touche que
`KWIC_PUCES` et `kwicRepere` dans `static/exploration.js`.

Ces trois points étaient les « différés » notés en toutes lettres au moment de livrer
ANA-3 et ANA-2 — ils ne venaient pas d'un audit mais de la revue de livraison.
