#!/usr/bin/env bash
# Restaure exclusivement vers un projet Compose de recette aux volumes vides.
set -euo pipefail
umask 077
AMBLUEO_INFRA_ARCHIVE="$(realpath -- "${1:?Indiquer une archive issue de backup.sh}")"
: "${COMPOSE_PROJECT_NAME:?Nom explicite requis pour la recette}"
[[ "$COMPOSE_PROJECT_NAME" == amblueo-recette-* ]]
[[ "${AMBLUEO_INFRA_CIBLE:-local}" == local ]]
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
AMBLUEO_INFRA_TEMP="$(mktemp -d)"
cleanup() { rm -rf -- "$AMBLUEO_INFRA_TEMP"; }
trap cleanup EXIT
for AMBLUEO_INFRA_FICHIER in SHA256SUMS postgres.dump justificatifs.tar; do
    tar -xOzf "$AMBLUEO_INFRA_ARCHIVE" "$AMBLUEO_INFRA_FICHIER" > "$AMBLUEO_INFRA_TEMP/$AMBLUEO_INFRA_FICHIER"
done
(cd "$AMBLUEO_INFRA_TEMP" && sha256sum -c SHA256SUMS)
./ops/compose.sh up -d --wait db
./ops/compose.sh exec -T db sh -ec '
    test "$(psql -X -Atq -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*) FROM pg_tables WHERE schemaname = current_schema()")" = 0
'
./ops/compose.sh run --rm -T --no-deps web sh -ec 'test -z "$(ls -A /data/private)"'
./ops/compose.sh exec -T db sh -ec 'pg_restore -1 --exit-on-error --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$AMBLUEO_INFRA_TEMP/postgres.dump"
./ops/compose.sh run --rm -T --no-deps web tar --no-same-owner --no-same-permissions -C /data/private -xf - < "$AMBLUEO_INFRA_TEMP/justificatifs.tar"
./ops/compose.sh run --rm -T --no-deps web python manage.py migrate --check
printf '%s\n' 'Restauration chargée. Vérifier les soldes et un justificatif avant de terminer la recette.'
