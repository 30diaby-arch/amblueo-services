#!/usr/bin/env bash
# Prend une sauvegarde cohérente pendant une fenêtre d'arrêt de Django.
set -euo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
: "${AMBLUEO_INFRA_DESTINATION_SAUVEGARDE:?Indiquer SSH utilisateur@serveur:/chemin}"
[[ "$AMBLUEO_INFRA_DESTINATION_SAUVEGARDE" =~ ^[a-zA-Z0-9_.-]+@[a-zA-Z0-9.-]+:/[a-zA-Z0-9_./-]+$ ]]
AMBLUEO_INFRA_TEMP="$(mktemp -d)"
AMBLUEO_INFRA_DATE="$(date -u +%Y%m%dT%H%M%SZ)"
AMBLUEO_INFRA_ARCHIVE="amblueo-${AMBLUEO_INFRA_DATE}.tar.gz"
AMBLUEO_INFRA_RELANCER=0

cleanup() {
    AMBLUEO_INFRA_RESULTAT=$?
    if [[ "$AMBLUEO_INFRA_RELANCER" == 1 ]]; then
        ./ops/compose.sh up -d web proxy || AMBLUEO_INFRA_RESULTAT=1
    fi
    rm -rf -- "$AMBLUEO_INFRA_TEMP"
    exit "$AMBLUEO_INFRA_RESULTAT"
}
trap cleanup EXIT
if [[ -n "$(./ops/compose.sh ps --status running -q web)" ]]; then
    AMBLUEO_INFRA_RELANCER=1
    ./ops/compose.sh stop proxy web
fi
./ops/compose.sh exec -T db sh -ec 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$AMBLUEO_INFRA_TEMP/postgres.dump"
./ops/compose.sh run --rm -T --no-deps web tar -C /data/private -cf - . > "$AMBLUEO_INFRA_TEMP/justificatifs.tar"
if [[ "$AMBLUEO_INFRA_RELANCER" == 1 ]]; then
    ./ops/compose.sh up -d --wait web proxy
    AMBLUEO_INFRA_RELANCER=0
fi
(
    cd "$AMBLUEO_INFRA_TEMP"
    sha256sum postgres.dump justificatifs.tar > SHA256SUMS
    tar -czf "$AMBLUEO_INFRA_ARCHIVE" SHA256SUMS postgres.dump justificatifs.tar
)
rsync -e 'ssh -o BatchMode=yes' -- "$AMBLUEO_INFRA_TEMP/$AMBLUEO_INFRA_ARCHIVE" "${AMBLUEO_INFRA_DESTINATION_SAUVEGARDE%/}/"
mkdir -p backups
date -u +%s > backups/derniere-sauvegarde-epoch
printf '%s\n' "$AMBLUEO_INFRA_ARCHIVE"
