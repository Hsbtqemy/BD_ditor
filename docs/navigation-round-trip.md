# Navigation, état d'URL et round-trip — invariants (Lot 5 transverse)

> Conception + implémentation le 2026-06-15. **Statut : implémenté.** Documente le
> modèle de navigation entre les trois surfaces (Visionneuse, Recherche, Exploration)
> et les invariants à respecter pour ne pas le casser.

## 1. Le scénario cible

Le « round-trip » des surfaces d'analyse : *je vois une occurrence → j'ouvre la
Visionneuse sur la région exacte → je corrige → je reviens à ma place* (recherche /
exploration intacte). Plus la **reprise d'état** : recharger n'importe quelle page
rouvre exactement au même endroit.

## 2. Tout l'état vit dans l'URL

Chaque surface **encode son état dans la query string** et le **restaure au
chargement**. Conséquence : un reload, un partage de lien ou un retour navigateur
retombent sur le même état. Aucune session serveur, aucun `localStorage` requis.

| Surface | Paramètres encodés | Écrit l'URL | Restaure au chargement |
|---|---|---|---|
| Visionneuse (`/`) | `album`, `planche`, `region`, `retour` | `syncUrl()` | `applyDeepLink()` |
| Recherche (`/recherche`) | `q`, `album`, `type`, `pos`, `lemme`, `morph`, `provenance`, `tags`, `retour` | `search()` | `restoreFromUrl()` |
| Exploration (`/exploration`) | `champ`, `compare`, filtres A (nus) + B (`b_*`), `retour` | `run()` via `stateParams()` | `restoreFromUrl()` |

**Invariant 1 — `INITIAL_QS`.** Chaque page capte `location.search` dans une
constante `INITIAL_QS` **avant** tout chargement, parce que l'écriture d'URL
(`syncUrl`/`search`/`run`) réécrit l'URL aussitôt et effacerait le deep-link
d'origine. Toute lecture du deep-link passe par `INITIAL_QS`, jamais par
`location.search` courant.

**Invariant 2 — l'écriture d'URL préserve tout ce qu'elle ne gère pas.** Les
fonctions d'écriture reconstruisent l'URL à partir de zéro ; elles **doivent
re-poser `retour`** (sinon le bouton « ← Retour » meurt au premier rendu). C'est
le cas de `syncUrl()` (Visionneuse) et `stateParams()` (Exploration).

## 3. La chaîne `retour`

Le paramètre `retour` porte **l'URL complète d'où l'on vient**, URL-encodée. Il se
**chaîne** : chaque maillon embarque l'URL du précédent, qui contient déjà son
propre `retour`.

```text
Exploration ──drillUrl()──▶ /recherche?…&retour=<URL exploration>
Recherche   ──lien ✏️─────▶ /?album=…&region=…&retour=<URL recherche (qui contient retour exploration)>
Visionneuse ──« ← Retour »─▶ <URL recherche>  (filtres intacts + son retour exploration)
Recherche   ──« ← Retour »─▶ <URL exploration> (sous-corpus A/B intacts)
```

Ainsi un aller `Exploration → Recherche → Visionneuse` se déroule en
`← Retour → ← Retour` sans rien perdre.

**Invariant 3 — `setupBack()` identique partout.** Les trois surfaces ont la même
fonction `setupBack()` : si `retour` (depuis `INITIAL_QS`) existe → bouton
`#back-link` pointant dessus ; sinon, si le `document.referrer` est une autre page
de l'app → `history.back()` ; sinon le bouton reste masqué. Garder les trois
copies synchrones.

## 4. Anti-course (chargements asynchrones concurrents)

Chaque surface garde un **jeton de fraîcheur** incrémenté à chaque action ; une
réponse asynchrone n'est appliquée que si son jeton est encore le plus récent.
Sans ça, un deep-link qui sélectionne une planche pendant que la 1ʳᵉ planche
auto-sélectionnée charge encore peut voir ses régions écrasées.

| Surface | Jeton | Pourquoi |
|---|---|---|
| Visionneuse | `plancheGen` | deep-link vs auto-sélection de la 1ʳᵉ planche (cf. commit 37f98f3) |
| Recherche | `searchGen` | frappe rapide / filtres : ignore les réponses périmées |
| Exploration | `state.gen` | changements de champ/filtres pendant un calcul de distribution |

**Invariant 4.** Toute fonction async qui applique un résultat dans le DOM doit
capturer son jeton en entrée et vérifier qu'il est toujours courant avant d'écrire.

## 5. Aperçu en place (Recherche)

Pour les cas simples, `openPreview()` montre la région (image + texte + note/tags)
**en lecture seule** sans quitter la Recherche → évite un round-trip complet quand
il s'agit juste de regarder. Le lien ✏️ du panneau ouvre la Visionneuse pour
*éditer* (avec `retour`).

## 6. Vérification

Pas de tests front automatisés dans le dépôt → la vérification du round-trip est
**manuelle** : `Exploration → (drill) → Recherche → (✏️) → Visionneuse → ← Retour
→ Recherche (filtres intacts) → ← Retour → Exploration (A/B intacts)`, plus un
reload sur chaque surface pour confirmer la reprise d'état.
