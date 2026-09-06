#!/usr/bin/env bash
#
# Déclenche `deployer.sh` quand `origin/main` a bougé — et refuse dans les cas où la
# décision appartient à un humain.
#
# Le déploiement se TIRE, il ne se pousse pas. Rien n'est confié à GitHub : aucune clé
# SSH de production chez un tiers, aucun port ouvert, aucun secret qui quitte la machine.
# Ce script fait ce qu'un opérateur ferait, à l'heure où il ne le fait pas.
#
#   ~/BD_ditor/deploy/veille-deploiement.sh
#   (posé sur un timer systemd — cf. deploy/systemd/, et docs/exploitation.md § 5)
#
# Il n'ajoute qu'UNE règle à `deployer.sh`, qui garde toutes les siennes : une mise à jour
# qui change `SCHEMA_VERSION` ne se déploie pas toute seule. `database._migrate()` est à
# sens unique et refuse de rétrograder ; l'en-tête de `deployer.sh` dit déjà que « la
# décision appartient à un humain qui a lu les journaux ». Automatiser le geste ne doit pas
# automatiser cette décision-là.
#
# CE QU'IL N'ÉCRIT PAS DANS LE CLONE, et c'est un piège qu'on évite exprès : un fichier
# d'état déposé là rendrait l'arbre SALE, et `deployer.sh` refuse de déployer sur un arbre
# sale — la veille se serait bloquée elle-même au deuxième passage. Le témoin d'échec vit
# donc HORS du clone (`$BD_VEILLE_ETAT`, sinon ~/.local/state/bd-deploiement).
#
# Et il existe parce que sans lui le signal d'échec ne survivait pas cinq minutes : un
# déploiement qui échoue a déjà fait avancer `HEAD` (le pull précède tout le reste), si
# bien qu'au tir suivant la veille aurait dit « rien à faire », serait sortie en 0, et
# l'unité `failed` serait redevenue verte. Un échec de trois heures du matin aurait été
# invisible à trois heures cinq.
#
# Codes de retour :
#   0  rien à faire, ou déploiement mené à bien
#   1  REFUS — la décision revient à un humain ; l'unité systemd passe `failed`, ce qui
#      est le seul endroit où un refus se VOIT (`systemctl status bd-deploiement`)
#   2  erreur d'usage
set -euo pipefail

simulation=0
case "${1:-}" in
  --simulation) simulation=1 ;;
  "")           ;;
  -h|--aide)    sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *)            echo "option inconnue : $1" >&2; exit 2 ;;
esac

racine="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$racine"

dire()  { printf '   %s\n' "$*"; }
refus() { printf 'REFUS %s\n' "$*" >&2; exit 1; }

etat="${BD_VEILLE_ETAT:-$HOME/.local/state/bd-deploiement}"
temoin="$etat/echec"

# ── Est-on bien sur l'instance ? ─────────────────────────────────────────────
[ -d .git ] || refus "ce n'est pas un dépôt git — la veille s'attend au clone du VPS"
[ -f deploy/.env ] || refus "deploy/.env est absent : cette machine n'est pas l'instance"

# La branche DÉPLOYÉE est `main`, et c'est une décision (cf. pilotage/journal.config.mjs).
# La veille refuse ailleurs plutôt que de suivre la branche courante : sur une machine
# restée par accident sur `dev`, « suivre l'amont » déploierait du travail en cours.
branche="$(git rev-parse --abbrev-ref HEAD)"
[ "$branche" = "main" ] || refus "la veille ne déploie que depuis 'main' ; la branche courante est '$branche'"

git fetch --quiet origin main || refus "git fetch a échoué — pas de réseau, ou l'accès au dépôt a changé"

ici="$(git rev-parse HEAD)"
la="$(git rev-parse origin/main)"

# ── Un déploiement précédent a-t-il échoué SUR CETTE CIBLE ? ─────────────────
# Le témoin nomme le commit qu'on s'apprêtait à déployer, et c'est à LUI qu'on le compare
# — pas à `HEAD`. Les deux ne coïncident pas toujours : `deployer.sh` peut échouer avant
# son `pull` (arbre sale) comme après (suite rouge), et seule la cible est commune aux
# deux cas. Conséquence voulue : un commit neuf sur `main` est une nouvelle tentative,
# tandis qu'une cible inchangée reste refusée jusqu'à ce qu'un humain s'en occupe.
if [ -f "$temoin" ] && [ "$(cat "$temoin" 2>/dev/null)" = "$la" ]; then
  refus "un déploiement a ÉCHOUÉ sur ${la:0:7}, et l'instance sert peut-être encore la
      version d'avant. La veille ne réessaie pas toute seule : un échec rejoué toutes les
      cinq minutes n'est plus un signal, c'est du bruit.
          journalctl -u bd-deploiement.service -n 80
          cd ~/BD_ditor && ./deploy/deployer.sh     # une fois la cause traitée
      Pousser un commit de plus sur main relance la veille ; sinon : rm $temoin"
fi

# ── Y a-t-il quelque chose à faire ? ─────────────────────────────────────────
if [ "$ici" = "$la" ]; then
  dire "rien à faire — main est à ${ici:0:7}"
  exit 0
fi

# `main` a RECULÉ : quelqu'un a réécrit l'histoire, ou déployé une révision antérieure.
# `deployer.sh` ne revient jamais en arrière tout seul, et pour une raison qui vaut ici
# aussi : la base a peut-être migré depuis.
if git merge-base --is-ancestor "$la" "$ici"; then
  refus "origin/main (${la:0:7}) est en ARRIÈRE de ce qui est déployé (${ici:0:7}).
      Revenir en arrière n'est pas un déploiement : la base a peut-être migré depuis,
      et \`_migrate()\` refuse de rétrograder. À trancher à la main."
fi

# Divergence : `deployer.sh` tire en `--ff-only` et échouerait. On le dit AVANT, parce
# qu'un échec répété toutes les cinq minutes ne s'explique pas tout seul.
if ! git merge-base --is-ancestor "$ici" "$la"; then
  refus "origin/main a DIVERGÉ de ce qui est déployé — pas d'avance rapide possible.
      Quelqu'un a commité sur le VPS, ou main a été réécrit. À trancher à la main."
fi

dire "main a avancé : ${ici:0:7} -> ${la:0:7} ($(git rev-list --count "$ici..$la") commit(s))"

# ── La règle que cette veille ajoute, et la seule ────────────────────────────
version_schema() {
  git show "$1:database.py" 2>/dev/null \
    | grep -m1 -oE '^SCHEMA_VERSION[[:space:]]*=[[:space:]]*[0-9]+' \
    | grep -oE '[0-9]+$'
}

avant_v="$(version_schema "$ici" || true)"
apres_v="$(version_schema "$la" || true)"

# Illisible des deux côtés : on ne peut pas conclure, donc on ne déploie pas. Fermeture
# par défaut — un « je ne sais pas » qui déploierait serait la pire des trois réponses.
if [ -z "$avant_v" ] || [ -z "$apres_v" ]; then
  refus "SCHEMA_VERSION illisible (déployé='${avant_v:-?}', cible='${apres_v:-?}').
      Impossible de dire si cette mise à jour porte une migration : on ne déploie pas.
      Vérifier que \`database.py\` porte bien une ligne 'SCHEMA_VERSION = <n>'."
fi

if [ "$avant_v" != "$apres_v" ]; then
  refus "cette mise à jour MIGRE le schéma : v$avant_v -> v$apres_v.
      \`_migrate()\` est à sens unique et refuse de rétrograder ; remettre l'ancien code
      sur une base déjà migrée serait pire que l'incident qu'on croirait réparer.
      Sauvegarder, puis déployer à la main :
          cd ~/BD_ditor && ./deploy/deployer.sh"
fi

dire "schéma inchangé (v$avant_v) — cette mise à jour ne migre pas"

# ── Passer la main au script, qui garde toutes ses gardes ────────────────────
if [ "$simulation" = 1 ]; then
  dire "SIMULATION — on s'arrêterait ici en lançant ./deploy/deployer.sh"
  exit 0
fi

# `exec` remplacerait ce processus, et la veille ne saurait rien de l'issue — or c'est
# précisément ce qu'elle doit retenir.
dire "lancement de ./deploy/deployer.sh"
if ./deploy/deployer.sh; then
  rm -f "$temoin"
  dire "déploiement mené à bien — ${la:0:7}"
  exit 0
fi

mkdir -p "$etat"
printf '%s' "$la" > "$temoin"
refus "le déploiement de ${la:0:7} a ÉCHOUÉ. Le témoin est posé dans $temoin :
      la veille ne réessaiera pas seule, et le prochain tir le redira au lieu de
      conclure qu'il n'y a rien à faire."
