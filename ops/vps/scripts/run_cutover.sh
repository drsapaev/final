#!/usr/bin/env bash
set -euo pipefail

: "${APP_ENV:=staging}"
: "${APP_ROOT:=/opt/clinic}"

BACKEND_DIR="${APP_ROOT}/backend"
BACKEND_ENV_FILE="${BACKEND_DIR}/.env.${APP_ENV}"

if [[ ! -f "${BACKEND_ENV_FILE}" ]]; then
  echo "Missing ${BACKEND_ENV_FILE}" >&2
  exit 1
fi

pushd "${BACKEND_DIR}" >/dev/null
set -a
source "${BACKEND_ENV_FILE}"
set +a
"${BACKEND_DIR}/.venv/bin/python" scripts/run_emr_cutover.py --pretty
popd >/dev/null
