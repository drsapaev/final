#!/usr/bin/env bash
set -euo pipefail

: "${APP_ENV:=staging}"
: "${APP_ROOT:=/opt/clinic}"

fail() {
  echo "$1" >&2
  exit 1
}

validate_identifier() {
  local name="$1"
  local value="$2"
  if [[ ! "${value}" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,62}$ ]]; then
    fail "${name} must use letters, digits, underscores, or hyphens; max 63 chars; must start with a letter or digit"
  fi
}

validate_app_root() {
  local name="$1"
  local value="$2"
  if [[ ! "${value}" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
    fail "${name} must be an absolute Unix path using only letters, digits, dots, underscores, hyphens, and slashes"
  fi
}

validate_identifier "APP_ENV" "${APP_ENV}"
validate_app_root "APP_ROOT" "${APP_ROOT}"

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
