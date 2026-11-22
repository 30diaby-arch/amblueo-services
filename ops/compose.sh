#!/usr/bin/env bash
# Lance Compose depuis le dépôt, indépendamment du dossier de l'appelant.
set -euo pipefail
AMBLUEO_INFRA_RACINE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$AMBLUEO_INFRA_RACINE"
AMBLUEO_INFRA_ARGUMENTS=(-f compose.yaml)
if [[ "${AMBLUEO_INFRA_CIBLE:-local}" == production ]]; then
    AMBLUEO_INFRA_ARGUMENTS+=(-f compose.prod.yaml)
fi
exec docker compose "${AMBLUEO_INFRA_ARGUMENTS[@]}" "$@"
