#!/usr/bin/env bash
# Lance Compose depuis le dépôt, indépendamment du dossier de l'appelant.
set -euo pipefail
AMBLUEO_INFRA_RACINE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$AMBLUEO_INFRA_RACINE"
export AMBLUEO_INFRA_FICHIER_ENV="${AMBLUEO_INFRA_FICHIER_ENV:-Operations/.env}"
AMBLUEO_INFRA_ARGUMENTS=(--project-directory "$AMBLUEO_INFRA_RACINE" --env-file "$AMBLUEO_INFRA_FICHIER_ENV" -f Operations/compose.yaml)
case "${AMBLUEO_INFRA_CIBLE:-local}" in
    local) ;;
    recette|production) AMBLUEO_INFRA_ARGUMENTS+=(-f Operations/compose.prod.yaml) ;;
    *) printf 'Cible Compose inconnue. Utiliser local, recette ou production.\n' >&2; exit 2 ;;
esac
if [[ "${AMBLUEO_INFRA_POSTFIX_HOTE:-}" == 1 ]] ||
    { [[ ! -v AMBLUEO_INFRA_POSTFIX_HOTE ]] && grep -qFx 'AMBLUEO_INFRA_POSTFIX_HOTE=1' "$AMBLUEO_INFRA_FICHIER_ENV"; }; then
    AMBLUEO_INFRA_ARGUMENTS+=(-f Operations/compose.postfix.yaml)
fi
exec docker compose "${AMBLUEO_INFRA_ARGUMENTS[@]}" "$@"
