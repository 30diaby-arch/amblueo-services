#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

AMBLUEO_INFRA_REVISION=${1:-}
if [[ $# -eq 0 ]]; then
    IFS= read -r AMBLUEO_INFRA_REVISION
fi
if [[ $# -gt 1 || ! "$AMBLUEO_INFRA_REVISION" =~ ^[0-9a-f]{40}$ ]]; then
    printf 'Indiquer le SHA Git complet à déployer.\n' >&2
    exit 2
fi

exec 9>"$(git rev-parse --git-path amblueo-deploiement.lock)"
flock -n 9 || { printf 'Un déploiement est déjà en cours.\n' >&2; exit 1; }
if [[ "$(git branch --show-current)" != main || -n "$(git status --porcelain)" ]]; then
    printf 'Le dépôt de recette doit être sur main avec un espace de travail propre.\n' >&2
    exit 1
fi
git fetch origin main
git merge-base --is-ancestor "$AMBLUEO_INFRA_REVISION" FETCH_HEAD
git merge-base --is-ancestor HEAD "$AMBLUEO_INFRA_REVISION"
git merge --ff-only "$AMBLUEO_INFRA_REVISION"

export AMBLUEO_INFRA_CIBLE=recette
./Operations/compose.sh config --quiet
./Operations/compose.sh build web
./Operations/compose.sh up -d --wait --wait-timeout 120 db
./Operations/compose.sh stop proxy web
./Operations/compose.sh run --rm -T --no-deps web python manage.py migrate --noinput
./Operations/compose.sh run --rm -T --no-deps web python manage.py collectstatic --noinput
./Operations/compose.sh up -d --wait --wait-timeout 120
./Operations/compose.sh exec -T proxy nginx -t
./Operations/compose.sh ps
printf 'Révision déployée : %s\n' "$AMBLUEO_INFRA_REVISION"
