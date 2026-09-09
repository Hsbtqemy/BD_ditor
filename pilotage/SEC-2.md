---
chantier: SEC-2
statut: livré
---

# SEC-2 — CSP maintenant, CSRF avec les sessions

**Arrêté sur** — le commit `ddc11fe`, 2026-09-09 : **les DEUX zones sont closes.** La CSP
le 2026-08-31 (`584d607`), avant la première exposition — c'est l'ordre que l'audit et
`docs/deploiement-docker.md` demandaient, et il a été tenu. Le CSRF aujourd'hui, quatre
jours après qu'INFRA-1 lui a donné un sens.

**Ce que la mesure a déplacé.** La zone CSRF attendait « une session à voler », et il y en
avait une depuis le 2026-09-05. Mais ce n'est pas la session qui ouvrait la porte : sur
72 routes mutantes, 61 étaient déjà hors d'atteinte — méthode ou Content-Type « non
simples », donc préflight, et l'application ne sert aucun en-tête CORS (vérifié dans tout
le dépôt : aucun). **Onze restaient forgeables par un `<form>`**, et le trou n'était pas
l'absence de `SameSite` mais le domaine PARENT du cookie. Le chantier a donc coûté ce
qu'annonçait la fiche, pour une raison qu'elle n'annonçait pas.

**La moitié du coût était ailleurs que dans la garde.** Neuf fichiers de test et un outil
parlent à l'application hors de la fixture `client` — dont six fichiers e2e qu'une
première passe de relecture avait manqués, et `tools/semer_demo.py`, qui mourait en 403 dès
le premier tag sans qu'aucun test ne le dise (`tools/` est hors couverture).

**Le blocage est LEVÉ — 2026-09-05.** INFRA-1 est livré : l'instance sert en HTTPS sur `bd.edito-revue.fr`, derrière Authelia, avec des comptes nommés et des sessions réelles. La raison de la mise en attente n'existe plus, et le statut change avec elle : laisser `différé` ferait annoncer par la fresque qu'on attend une instance qui tourne déjà.

Le statut devient `interrompu` et non `à venir`, et c'est l'outil qui l'impose : la fiche porte UN commit de code, celui de la zone CSP. Un `à venir` démenti par son propre historique vaudrait moins que le mot approximatif.

**Rejoué une dernière fois le 2026-09-09 : le statut est `livré`, et c'est celui-là
qui vaut.** Les deux paragraphes ci-dessus sont la trace du 2026-09-05 — gardée, parce
qu'elle explique pourquoi la fiche a porté `interrompu` quatre jours plutôt qu'`à venir`.

Trois faits expliquent que ç'ait été si peu cher, et le premier est le plus utile à
retenir : **la sévérité était déjà atteignable, personne ne l'avait déclarée**. Zéro
`<script>` inline, zéro `<style>`, zéro `onclick=`, zéro `eval`, aucune ressource externe
dans les quatre gabarits — `script-src 'self'` sans `'unsafe-inline'` n'a demandé AUCUNE
modification d'application.

**Point de départ** — aucun en-tête Content-Security-Policy n'était servi, et les appels
`apiSend` POST/PUT/DELETE n'envoient ni jeton ni en-tête personnalisé. Risque faible en
mono-poste local, à traiter **avant** toute exposition réseau.

**Mesuré le 2026-09-05, sur l'instance en service.** L'en-tête est :

```
Set-Cookie: authelia_session=…; domain=edito-revue.fr; path=/;
            HttpOnly; secure; SameSite=Lax
```

`SameSite=Lax` **ferme la CSRF inter-sites classique** : un POST déclenché depuis un site
tiers n'emporte pas ce cookie, et `fetch` cross-origin non plus. Le chantier cesse donc
d'être urgent, et c'est une mesure qui le dit, pas une intuition.

**Ce qui reste ouvert tient dans un mot de cette ligne : `domain=edito-revue.fr`.** Le
cookie est posé sur le domaine PARENT, et c'est nécessaire — Authelia doit partager la
session entre `auth.` et `bd.`. Or `SameSite` raisonne par domaine ENREGISTRABLE et non
par origine : `edito-revue.fr` et n'importe quel autre sous-domaine sont *same-site* vis-à-vis
de `bd.edito-revue.fr`, et `Lax` n'y oppose rien. Le cookie leur est envoyé.

Le risque est donc CONDITIONNEL, et sa condition n'est pas chez nous : il faut qu'un
attaquant puisse faire émettre une requête depuis un `*.edito-revue.fr`, c'est-à-dire une
XSS ou une injection de contenu sur l'autre site que ce serveur héberge. Nous ne
contrôlons pas ce site, et c'est précisément pourquoi une protection CSRF côté application
garde du sens : elle ne dépend d'aucune hypothèse sur les voisins.

## Reste

### CSP — faisable tout de suite
- [x] **Un en-tête CSP est servi, et la console est vide** — mais « vérifié console navigateur vide » se contemplait, alors c'est devenu exécutable : `tests/test_csp.py` charge les sept surfaces (les cinq pages, `/docs`, `/redoc` — six et quatre jusqu'au 2026-09-07, `/administration` s'y étant ajoutée avec UX-10) dans un vrai Chromium et écoute l'événement `securitypolicyviolation`, qui porte la directive, la ressource et la ligne — là où un message de console est une chaîne à relire. Il a trouvé DEUX choses qu'aucune lecture de source ne pouvait voir : le `<link rel="icon" href="data:,">` que portent les gabarits — quatre à la mesure, cinq depuis, `administration.html` le portant aussi (vérifié le 2026-09-08) — et qui exigeait `data:` dans `img-src`, et le logo que ReDoc va chercher sur `cdn.redoc.ly` depuis l'INTÉRIEUR de son bundle — une URL absente du HTML servi. Ce dernier reste BLOQUÉ et déclaré dans `BLOCAGES_ADMIS` avec sa raison : on n'ouvre pas un hôte tiers pour une image décorative
- [x] **Le script inline est interdit, et la seule tolérance est bornée et écrite** — `script-src 'self'`, sans `'unsafe-inline'` ni `'unsafe-eval'`. La tolérance porte sur `style-src` seulement, pour dix attributs `style="width:…%"` qui transportent des valeurs CALCULÉES (barres, heatmap, jauges d'accord) et ne peuvent pas rejoindre la feuille de style. `style-src-elem 'self'` reprend d'une main ce que `style-src` donne de l'autre : aucun `<style>` n'existe, donc le canal ÉLÉMENT est strict gratuitement, et seul l'attribut reste ouvert ; un navigateur qui ignore `-elem` retombe sur la règle permissive — plus faible, jamais cassé
- [x] **L'audit e2e reste vert, après avoir failli mourir de la CSP** : `test_e2e_a11y.py` injectait axe par `page.add_script_tag(content=…)`, c'est-à-dire un `<script>` inline, que `script-src 'self'` bloque net. C'est `page.evaluate` désormais — le protocole de débogage, hors du modèle de sécurité de la page. C'est ce qu'on veut d'un instrument de mesure : qu'il n'ait pas besoin qu'on desserre ce qu'il vient vérifier

### CSRF — close le 2026-09-09
- [x] **Une protection CSRF est en place sur les routes mutantes.** La prémisse de cette case avait déjà changé le 2026-09-05 — elle disait « aucune session de navigateur à voler », vrai en mono-poste et faux depuis Authelia. La mesure a déplacé une seconde fois : `Lax` fermait bien l'inter-sites, mais le cookie porte `domain=edito-revue.fr`, le domaine PARENT, et `SameSite` raisonne par domaine ENREGISTRABLE — tout `*.edito-revue.fr` est *same-site* et le reçoit. **Un middleware refuse désormais toute POST/PUT/PATCH/DELETE qui ne porte ni `X-BD-Requete` ni un `Sec-Fetch-Site: same-origin` posé par le navigateur.** La CSP n'y touchait toujours pas : `form-action 'self'` borde les formulaires, pas les requêtes `fetch`
- [x] **`same-site` est REFUSÉ, et c'est le cas qui motivait tout le chantier** — l'accepter aurait donné une garde qui refuse ce qui était déjà refusé (l'inter-sites, que `Lax` fermait) et laisse passer ce qui ne l'était pas. `test_csrf.py` l'éprouve sur `same-site` ET `cross-site`
- [x] **Les deux mécanismes tiennent chacun sans l'autre** — l'en-tête seul suffit (un navigateur d'avant Firefox 90 ou Safari 16.4 n'envoie pas `Sec-Fetch-Site` : s'en remettre à lui seul aurait fait dépendre la protection de la version du navigateur de la victime), et `Sec-Fetch-Site: same-origin` seul suffit (c'est ce qui laisse vivre le « Try it out » de `/docs`, qui n'a aucune raison de connaître notre en-tête). Un test par branche
- [x] **Le 403 de la garde sort AVEC la politique de sécurité** — Starlette applique les middlewares dans l'ordre INVERSE de leur déclaration, donc la garde est déclarée AVANT `_csp` pour être la plus INTERNE. Déclarée en dernier, elle serait devenue externe et son refus serait ressorti sans CSP, rendant fausse la promesse « sur TOUTE réponse » pour les seules réponses qu'on refuse. Rien ne rend cet ordre visible à la lecture — il tient à la POSITION de deux fonctions dans un fichier, qu'un déplacement anodin change sans le dire —, donc un test l'épingle en vérifiant l'en-tête CSP sur le 403
- [x] **Le nom de l'en-tête ne peut plus diverger entre Python et JavaScript.** C'était **le seul défaut de ce chantier qui aurait laissé la suite par défaut VERTE** : tous ses clients passent par la fixture `client`, qui lit `main.EN_TETE_REQUETE` et suivrait un renommage, pendant que le frontend garderait l'ancien nom et que chaque écriture de chaque surface repartirait en 403. Seul le navigateur l'aurait vu, douze minutes plus tard, et le marqueur `e2e` est exclu par défaut. `test_csrf.py` balaie donc `static/**/*.js` — un test qui lit le SOURCE, faible en général et exact ici puisque ce qu'on vérifie EST une graphie —, avec sa garde d'anti-aveuglement (un plancher de trois `method:` littéraux) et l'aveu écrit de ce qu'il ne prouve pas
- [x] **Rien de ce qui parle à l'API hors navigateur n'est resté cassé** — neuf fichiers de test et `tools/semer_demo.py`, mesuré dans les deux sens pour l'outil (403 sans l'en-tête, vert avec). Le mode d'échec mérite son nom : la réponse 403 se lit `{"detail": …}`, donc un `.json()["id"]` de fixture lève un **`KeyError`** — pas un 403 qu'on voit, une `KeyError`, douze minutes après le lancement du navigateur
- [x] **Le coût est écrit plutôt que découvert** — un client HTTP hors navigateur doit désormais poser `X-BD-Requete`, et le 403 le NOMME au lieu d'échouer en silence. `CLAUDE.md` porte les trois conséquences pour qui écrira du code ici (un `fetch` construit à la main doit poser l'en-tête lui-même ; un client de test *live* prend `ECRITURE` et non `ADMIN` ; un outil hors navigateur importe la constante plutôt que de recopier la graphie), `docs/hebergement-securite.md` la règle et sa raison

## Contexte

Fiche **scindée exprès en deux zones** : le backlog les traitait comme un seul ticket P3,
ce qui masquait que la moitié est faisable immédiatement. La CSP ne dépendait de rien ; le
CSRF n'avait aucun sens tant qu'il n'y avait pas de session à voler, donc il dépendait
d'INFRA-1 — **livré le 2026-09-05, et le cookie Authelia existe depuis**. Le découpage a
donc rendu ce qu'on en attendait : une moitié livrée dix jours avant que l'autre ne devienne
seulement possible.

~~La quatrième case restera ouverte tant qu'INFRA-1 n'aura pas abouti — c'est normal et
c'est l'information utile : la fiche ne se clora pas avant le déploiement.~~ **Tenu, et
dans l'ordre annoncé** : INFRA-1 le 2026-09-05, la case le 2026-09-09.

L'ordre importe. `docs/deploiement-docker.md` et l'audit s'accordent : ceci se traite
avant l'exposition réseau, pas après. **Tenu** : la CSP est posée avant qu'INFRA-1
n'aboutisse, donc avant la première exposition.

**Deux politiques, et c'est la décision de conception du chantier.** `/docs` et `/redoc`
sont engendrés par FastAPI depuis un CDN, avec du script inline : la politique stricte ne
les sécuriserait pas, elle les casserait. Ils reçoivent donc la LEUR — le CDN autorisé,
mais `object-src`, `base-uri` et `frame-ancestors` toujours fermés. On relâche ce qu'il
faut pour que la page vive, pas le principe. Les exempter aurait été plus simple à lire et
pire : un chemin sans politique est un chemin qu'il faut se rappeler d'avoir exempté, et
c'est exactement la forme d'oubli qu'AUTH-5 a passé la journée à fermer ailleurs.

**Ce que la CSP répare rétroactivement.** L'audit passe 1 relevait deux `innerHTML`
interpolant des labels de tags sans échapper, et recommandait DEUX correctifs :
« échapper systématiquement, ajouter une CSP ». Le premier a été fait depuis — vérifié le
2026-08-31, il ne reste aucune interpolation de donnée utilisateur hors `esc()`,
`textContent` ou `confirm()`. La CSP est le second, et sa valeur est d'être utile le jour
où l'échappement manquera quelque part : `script-src 'self'` bloque aussi bien un
`<script>` injecté qu'un attribut `onerror=`, qui est précisément la forme qu'aurait prise
ce défaut-là.
