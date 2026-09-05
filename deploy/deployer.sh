#!/usr/bin/env bash
#
# Déploie la dernière version sur le VPS, en refusant d'avancer à chaque endroit où
# l'on s'est déjà trompé.
#
#   ssh ubuntu@83.228.221.204
#   cd ~/BD_ditor && ./deploy/deployer.sh
#
# Ce n'est pas un raccourci pour les quatre commandes du runbook : c'est la liste des
# GARDES que ces quatre commandes n'ont pas. Chaque refus ci-dessous correspond à une
# panne réelle, datée, et documentée dans `docs/exploitation.md` § 4.
#
# Ce qu'il ne fait PAS, et c'est délibéré :
#
#   * il ne REVIENT JAMAIS EN ARRIÈRE tout seul. `database._migrate()` est à sens
#     unique et refuse de rétrograder : remettre l'ancien code sur une base déjà migrée
#     serait pire que l'incident qu'on croirait réparer. En cas d'échec il dit d'où l'on
#     vient et s'arrête — la décision appartient à un humain qui a lu les journaux.
#   * il ne touche ni à `.env` ni à `authelia/users_database.yml`. Aucun secret ne
#     passe par ici, ni en argument, ni à l'écran.
#   * il ne fait pas de sauvegarde. `GET /api/sauvegarde` et le dépôt ShareDocs sont des
#     gestes d'exploitation à part ; les enchaîner ici donnerait l'illusion d'un filet.
#
set -euo pipefail

URL_PAR_DEFAUT="https://bd.edito-revue.fr"
url="$URL_PAR_DEFAUT"
simulation=0
sans_suite=0
forcer=0

usage() {
  cat <<'FIN'
Usage : ./deploy/deployer.sh [options]

  --url URL        instance à contrôler après coup (défaut : https://bd.edito-revue.fr)
  --simulation     tout afficher, ne rien exécuter qui modifie l'instance
  --forcer         redéployer même si `git pull` n'a rien ramené
  --sans-suite     NE PAS jouer la suite dans l'image avant de déployer
                   (à n'employer qu'en urgence : c'est la garde qui a le plus servi)
  -h, --aide       cette aide
FIN
}

while [ $# -gt 0 ]; do
  case "$1" in
    --url)        url="${2:?--url attend une URL}"; shift 2 ;;
    --simulation) simulation=1; shift ;;
    --forcer)     forcer=1; shift ;;
    --sans-suite) sans_suite=1; shift ;;
    -h|--aide)    usage; exit 0 ;;
    *)            echo "option inconnue : $1" >&2; usage >&2; exit 2 ;;
  esac
done

# ── Affichage ────────────────────────────────────────────────────────────────
etape() { printf '\n\033[1m── %s\033[0m\n' "$*"; }
ok()    { printf '   ok   %s\n' "$*"; }
refus() { printf '\n\033[1;31mREFUS\033[0m %s\n' "$*" >&2; exit 1; }
faire() {
  if [ "$simulation" = 1 ]; then printf '   (simulation) %s\n' "$*"; else eval "$@"; fi
}

# ── 0. Préalables ────────────────────────────────────────────────────────────
etape "Préalables"

# Le script se situe LUI-MÊME plutôt que d'exiger d'être lancé d'un dossier donné : un
# `cd` oublié est la façon la plus banale de faire porter un `git pull` sur autre chose.
racine="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$racine"
ok "dépôt : $racine"

[ -d .git ] || refus "ce n'est pas un dépôt git — le script s'attend à être exécuté depuis le clone du VPS"
[ -f deploy/.env ] || refus "deploy/.env est absent : cette machine n'est pas l'instance déployée, ou la configuration a disparu"
command -v docker >/dev/null || refus "docker est introuvable"
docker compose version >/dev/null 2>&1 || refus "le greffon 'docker compose' est introuvable (v2 requise)"

# Un arbre sale sur un serveur veut dire que quelqu'un a édité en place. Le `pull` qui
# suit l'écraserait, ou échouerait à mi-chemin — précisément le scénario du 2026-09-05.
if [ -n "$(git status --porcelain)" ]; then
  git status --short
  refus "l'arbre de travail n'est pas propre : quelqu'un a modifié des fichiers en place. Trancher à la main AVANT de déployer."
fi
ok "arbre de travail propre"

# `git pull` sur un HEAD détaché ne suit rien et échoue d'une façon qui ne se lit pas.
branche="$(git rev-parse --abbrev-ref HEAD)"
[ "$branche" != "HEAD" ] || refus "HEAD est détaché : il n'y a aucune branche à suivre. Se replacer sur une branche (probablement 'main') avant de déployer."
ok "branche : $branche"

# La reconstruction installe torch, easyocr, ultralytics, spacy et opencv (roues CPU) :
# elle demande plusieurs gigaoctets. On AFFICHE le chiffre au lieu d'inventer un seuil —
# un refus fondé sur une valeur devinée bloquerait un déploiement légitime, et une panne
# de disque en pleine construction laisse des couches orphelines derrière elle.
racine_docker="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || true)"
[ -n "$racine_docker" ] || racine_docker=/
libre="$(df -Ph "$racine_docker" 2>/dev/null | awk 'NR==2 {print $4}')"
ok "espace libre sur $racine_docker : ${libre:-inconnu} — si c'est juste : docker system prune"

# ── 1. Récupérer, et VÉRIFIER que la ref a bougé ─────────────────────────────
etape "Récupération"

avant="$(git rev-parse HEAD)"
ok "avant : $(git log --oneline -1 --no-decorate)"

# `--ff-only` : une fusion sur un serveur n'est jamais voulue. Si la branche a divergé,
# c'est qu'on a commité ici, et il faut le regarder au lieu de le fusionner en silence.
faire "git pull --ff-only"

apres="$(git rev-parse HEAD)"

# LA garde du 2026-09-05. `git pull` peut mettre à jour l'arbre puis échouer à délier un
# fichier — un dossier appartenant à root suffit — et RENDRE 0 en laissant HEAD en
# arrière. Le VPS a vécu neuf commits de retard avec un `pull` qui semblait réussir.
if [ "$simulation" = 0 ] && [ "$avant" = "$apres" ]; then
  if [ "$forcer" = 0 ]; then
    echo "   rien de neuf : HEAD n'a pas bougé."
    echo "   Si vous ATTENDIEZ une mise à jour, c'est le symptôme du 2026-09-05 —"
    echo "   vérifiez les droits : ls -ld deploy/authelia  (doit appartenir à ubuntu)"
    echo "   Sinon, --forcer pour reconstruire quand même."
    exit 0
  fi
  ok "HEAD inchangé, mais --forcer demandé"
else
  ok "après : $(git log --oneline -1 --no-decorate)"
fi

# Un `pull` partiellement appliqué laisse des traces ici alors qu'il a rendu 0.
[ -z "$(git status --porcelain)" ] || {
  git status --short
  refus "l'arbre est sale APRÈS le pull : la mise à jour s'est appliquée à moitié"
}
ok "arbre encore propre après le pull"

# ── 2. La pile est-elle bien celle de cette instance ? ───────────────────────
etape "Configuration de la pile"

cd "$racine/deploy"

# Sans `COMPOSE_FILE`, Caddy réclame 80 et 443 — que nginx occupe déjà sur cet hôte.
# On ne le devine pas : on demande à Compose ce qu'il a résolu.
#
# Et l'on distingue « Compose a répondu, sans le port attendu » de « Compose n'a pas
# répondu ». Écrite en un seul `| grep`, cette garde annonçait COMPOSE_FILE manquant
# chaque fois que la commande ÉCHOUAIT, quelle qu'en soit la raison — un diagnostic faux
# envoie chercher une panne qui n'existe pas, ce qui est pire que pas de diagnostic.
if ! sortie_config="$(docker compose config 2>&1)"; then
  refus "\`docker compose config\` a échoué : la pile ne se résout pas. Ce n'est PAS un
      COMPOSE_FILE manquant — la commande elle-même n'a pas abouti. Sa sortie :

$(printf '%s' "$sortie_config" | sed 's/^/      /' | head -20)"
fi
# Deux questions distinctes, et deux messages distincts. La première — l'override
# est-il dans la pile résolue ? — se lit sur un chemin de volume, qui survit à toute
# normalisation. La seconde ne se pose que si la première répond oui.
if ! printf '%s' "$sortie_config" | grep -q "Caddyfile.derriere-proxy"; then
  refus "l'override 'derriere-proxy' n'est PAS dans la pile résolue — COMPOSE_FILE manque
      dans deploy/.env.
      Réparer :  echo 'COMPOSE_FILE=docker-compose.yml:docker-compose.derriere-proxy.yml' >> deploy/.env
      Sans lui, Caddy publie 80 et 443 : un \`docker compose up -d\` sans nom de service
      le recréerait ainsi, en collision avec le nginx qui sert l'autre site du serveur."
fi

# `docker compose config` NORMALISE la syntaxe courte des ports : `\"127.0.0.1:8080:80\"`
# devient une forme longue où `host_ip` et `published` vivent sur des LIGNES SÉPARÉES, si
# bien que la chaîne « 127.0.0.1:8080 » n'apparaît nulle part. Mesuré sur le VPS le
# 2026-09-05 — cette garde a refusé une pile parfaitement correcte, en annonçant une
# cause qu'elle n'avait pas vérifiée. On accepte donc les DEUX rendus : les versions de
# Compose ne s'accordent pas là-dessus, et un environnement donné n'en montre qu'un.
port_ok=0
if printf '%s' "$sortie_config" | grep -qE 'host_ip: *127\.0\.0\.1' &&
   printf '%s' "$sortie_config" | grep -qE 'published: *"?8080"?'; then
  port_ok=1                       # forme longue (Compose v2 récent)
fi
if printf '%s' "$sortie_config" | grep -qE '127\.0\.0\.1:8080'; then
  port_ok=1                       # forme courte (rendu non normalisé)
fi
if [ "$port_ok" = 0 ]; then
  refus "l'override est bien dans la pile, mais elle ne publie pas sur 127.0.0.1:8080.
      Quelqu'un a changé le port, ou Compose rend une TROISIÈME forme que ce script ne
      connaît pas. Vérifier à la main :
        docker compose config | grep -nE '8080|host_ip|derriere-proxy'"
fi
ok "override 'derriere-proxy' actif (127.0.0.1:8080)"

# Cohérence des domaines déclarés, AVANT de démarrer quoi que ce soit. Ne lit aucune
# valeur secrète : le script de contrôle ne rapporte que des noms de clés.
faire "python3 verifier_deploiement.py --config .env"
ok "configuration cohérente"

# ── 3. La suite DANS l'image ─────────────────────────────────────────────────
# QA-5, mesuré le 2026-08-27 : 451 tests verts dans le venv local et trois moteurs morts
# dans l'image, le même jour. Le venv n'est pas l'artefact livré.
if [ "$sans_suite" = 1 ]; then
  printf '\n\033[1;33mSUITE SAUTÉE\033[0m — --sans-suite. Le venv local ne dit rien de cette image.\n'
else
  etape "Suite de tests dans l'image (quelques minutes)"
  cd "$racine"
  faire "docker build -f deploy/Dockerfile --target test -t bdediteur:suite ."
  faire "docker run --rm bdediteur:suite"
  ok "suite verte dans l'image"
  cd "$racine/deploy"
fi

# ── 4. Déployer ──────────────────────────────────────────────────────────────
etape "Déploiement"

# `up -d --build` et non `restart` : `restart` relance le conteneur EXISTANT avec
# l'environnement qu'il avait à sa création, donc sans relire .env ni le nouveau code.
faire "docker compose up -d --build app"
faire "docker compose ps"

# ── 5. Contrôler depuis DEHORS ───────────────────────────────────────────────
etape "Contrôle en anonyme, depuis l'extérieur"

if [ "$simulation" = 1 ]; then
  echo "   (simulation) python3 verifier_deploiement.py --url $url"
  exit 0
fi

# L'application met quelques secondes à répondre après un redémarrage : on attend
# qu'elle réponde plutôt que de la déclarer morte au premier essai.
for essai in $(seq 1 20); do
  if curl -fsS -o /dev/null --max-time 5 "$url" 2>/dev/null; then break; fi
  [ "$essai" = 20 ] && refus "l'instance ne répond toujours pas après 20 essais.
      Journaux : cd $racine/deploy && docker compose logs --tail 80 app
      État AVANT ce déploiement : ${avant:0:7}
      NE PAS revenir en arrière sans avoir lu les journaux : les migrations de schéma
      sont à sens unique, et remettre l'ancien code sur une base migrée est pire."
  sleep 3
done
ok "l'instance répond"

if ! python3 verifier_deploiement.py --url "$url"; then
  refus "le contrôle externe a échoué — l'instance TOURNE mais quelque chose ne va pas.
      Ne pas rétrograder par réflexe : lire d'abord ce que le contrôle a signalé.
      État AVANT ce déploiement : ${avant:0:7}"
fi

# ── Bilan ────────────────────────────────────────────────────────────────────
printf '\n\033[1;32mDÉPLOYÉ\033[0m  %s → %s\n' "${avant:0:7}" "${apres:0:7}"
git -C "$racine" log --oneline --no-decorate "$avant..$apres" | sed 's/^/   /' || true
