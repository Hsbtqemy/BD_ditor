---
chantier: SEC-2
statut: différé
---

# SEC-2 — CSP maintenant, CSRF avec les sessions

**Arrêté sur** — le commit `584d607`, 2026-08-31 : **la zone CSP est close**, la zone CSRF
reste entière et dépend toujours d'INFRA-1. D'où `différé` et non `interrompu` : ce n'est
pas un travail abandonné en route, c'est une moitié livrée et une moitié qui attend un
déploiement pour avoir un sens.

Trois faits expliquent que ç'ait été si peu cher, et le premier est le plus utile à
retenir : **la sévérité était déjà atteignable, personne ne l'avait déclarée**. Zéro
`<script>` inline, zéro `<style>`, zéro `onclick=`, zéro `eval`, aucune ressource externe
dans les quatre gabarits — `script-src 'self'` sans `'unsafe-inline'` n'a demandé AUCUNE
modification d'application.

**Point de départ** — aucun en-tête Content-Security-Policy n'était servi, et les appels
`apiSend` POST/PUT/DELETE n'envoient ni jeton ni en-tête personnalisé. Risque faible en
mono-poste local, à traiter **avant** toute exposition réseau.

## Reste

### CSP — faisable tout de suite
- [x] **Un en-tête CSP est servi, et la console est vide** — mais « vérifié console navigateur vide » se contemplait, alors c'est devenu exécutable : `tests/test_csp.py` charge les six surfaces (les quatre pages, `/docs`, `/redoc`) dans un vrai Chromium et écoute l'événement `securitypolicyviolation`, qui porte la directive, la ressource et la ligne — là où un message de console est une chaîne à relire. Il a trouvé DEUX choses qu'aucune lecture de source ne pouvait voir : le `<link rel="icon" href="data:,">` que portent les quatre gabarits (il fallait `data:` dans `img-src`), et le logo que ReDoc va chercher sur `cdn.redoc.ly` depuis l'INTÉRIEUR de son bundle — une URL absente du HTML servi. Ce dernier reste BLOQUÉ et déclaré dans `BLOCAGES_ADMIS` avec sa raison : on n'ouvre pas un hôte tiers pour une image décorative
- [x] **Le script inline est interdit, et la seule tolérance est bornée et écrite** — `script-src 'self'`, sans `'unsafe-inline'` ni `'unsafe-eval'`. La tolérance porte sur `style-src` seulement, pour dix attributs `style="width:…%"` qui transportent des valeurs CALCULÉES (barres, heatmap, jauges d'accord) et ne peuvent pas rejoindre la feuille de style. `style-src-elem 'self'` reprend d'une main ce que `style-src` donne de l'autre : aucun `<style>` n'existe, donc le canal ÉLÉMENT est strict gratuitement, et seul l'attribut reste ouvert ; un navigateur qui ignore `-elem` retombe sur la règle permissive — plus faible, jamais cassé
- [x] **L'audit e2e reste vert, après avoir failli mourir de la CSP** : `test_e2e_a11y.py` injectait axe par `page.add_script_tag(content=…)`, c'est-à-dire un `<script>` inline, que `script-src 'self'` bloque net. C'est `page.evaluate` désormais — le protocole de débogage, hors du modèle de sécurité de la page. C'est ce qu'on veut d'un instrument de mesure : qu'il n'ait pas besoin qu'on desserre ce qu'il vient vérifier

### CSRF — dépend d'INFRA-1
- [ ] Une protection CSRF est en place sur les routes mutantes, une fois que des sessions existent réellement. **Rien n'a changé de ce côté au 2026-08-31**, et c'est voulu : la CSP n'y touche pas (`form-action 'self'` borde les formulaires, pas les requêtes `fetch`), et il n'y a toujours aucune session de navigateur à voler — l'application n'authentifie personne, elle croit un en-tête posé par le proxy

## Contexte

Fiche **scindée exprès en deux zones** : le backlog les traitait comme un seul ticket P3,
ce qui masquait que la moitié est faisable immédiatement. La CSP ne dépend de rien ; le
CSRF n'a aucun sens tant qu'il n'y a pas de session à voler, donc dépend d'INFRA-1.

La quatrième case restera ouverte tant qu'INFRA-1 n'aura pas abouti — c'est normal et
c'est l'information utile : la fiche ne se clora pas avant le déploiement.

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
