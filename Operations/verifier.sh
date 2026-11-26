#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

if [[ $# -gt 1 || ( $# -eq 1 && "$1" != --affichage ) ]]; then
    printf 'Usage : %s [--affichage]\n' "$0" >&2
    exit 2
fi

export AMBLUEO_INFRA_CIBLE=local AMBLUEO_INFRA_POSTFIX_HOTE=0
export AMBLUEO_INFRA_FICHIER_ENV=Operations/.env.example AMBLUEO_INFRA_PORT_PROXY=
export AMBLUEO_INFRA_IMAGE="amblueo-validation-$$:local"
AMBLUEO_TEST_COMPOSE=(./Operations/compose.sh --project-name "amblueo-validation-$$")

nettoyer() {
    AMBLUEO_TEST_RESULTAT=$?
    if (( AMBLUEO_TEST_RESULTAT != 0 )); then
        "${AMBLUEO_TEST_COMPOSE[@]}" logs --no-color >&2 || true
    fi
    "${AMBLUEO_TEST_COMPOSE[@]}" down --volumes --rmi local || true
    if docker image inspect "$AMBLUEO_INFRA_IMAGE" >/dev/null 2>&1; then
        docker image rm "$AMBLUEO_INFRA_IMAGE" >/dev/null || true
    fi
    exit "$AMBLUEO_TEST_RESULTAT"
}
trap nettoyer EXIT

"${AMBLUEO_TEST_COMPOSE[@]}" config --quiet
"${AMBLUEO_TEST_COMPOSE[@]}" build web
"${AMBLUEO_TEST_COMPOSE[@]}" up -d --wait --wait-timeout 90 db
"${AMBLUEO_TEST_COMPOSE[@]}" run --rm -T --no-deps web sh -ec '
    python manage.py check
    python manage.py makemigrations --check --dry-run
    python manage.py test
'

if [[ ${1:-} == --affichage ]]; then
    "${AMBLUEO_TEST_COMPOSE[@]}" run --rm -T --no-deps web sh -ec '
        python manage.py migrate --noinput
        python manage.py collectstatic --noinput
        python manage.py seed_demo
    '
    "${AMBLUEO_TEST_COMPOSE[@]}" up -d --wait --wait-timeout 90
    AMBLUEO_TEST_ADRESSE=$("${AMBLUEO_TEST_COMPOSE[@]}" port proxy 80)
    "${AMBLUEO_TEST_COMPOSE[@]}" exec -T -e AMBLUEO_TEST_ORIGINE="http://$AMBLUEO_TEST_ADRESSE" \
        web python manage.py shell --verbosity 0 -c '
from os import environ
from django.template.loader import render_to_string

print(render_to_string("pilot/email/base.html", {
    "origin": environ["AMBLUEO_TEST_ORIGINE"],
    "subject": "Une tâche vous a été attribuée",
    "body": "La tâche « Valider les maquettes » vous a été attribuée.",
    "link": environ["AMBLUEO_TEST_ORIGINE"],
    "action": "Voir la tâche dans le projet",
}))
' |
        "${AMBLUEO_TEST_PYTHON:-python3}" Operations/verifier-affichage.py "http://$AMBLUEO_TEST_ADRESSE"
fi

printf 'Validation réussie.\n'
