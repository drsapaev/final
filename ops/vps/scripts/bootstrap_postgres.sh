#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <db_user> <db_password> <db_name>" >&2
  exit 1
fi

DB_USER="$1"
DB_PASSWORD="$2"
DB_NAME="$3"

validate_identifier() {
  local name="$1"
  local value="$2"
  if [[ ! "${value}" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]]; then
    echo "${name} must be a PostgreSQL identifier: letters, digits, underscores, max 63 chars, not starting with a digit" >&2
    exit 1
  fi
}

sql_literal() {
  local value="$1"
  local escaped="${value//\'/\'\'}"
  printf "'%s'" "${escaped}"
}

if [[ "${DB_PASSWORD}" == *$'\n'* || "${DB_PASSWORD}" == *$'\r'* ]]; then
  echo "db_password must not contain newline characters" >&2
  exit 1
fi

validate_identifier "db_user" "${DB_USER}"
validate_identifier "db_name" "${DB_NAME}"

DB_USER_LITERAL="$(sql_literal "${DB_USER}")"
DB_PASSWORD_LITERAL="$(sql_literal "${DB_PASSWORD}")"
DB_NAME_LITERAL="$(sql_literal "${DB_NAME}")"

ROLE_SQL="DO \$\$ "
ROLE_SQL+="DECLARE role_name text := ${DB_USER_LITERAL}; "
ROLE_SQL+="role_password text := ${DB_PASSWORD_LITERAL}; "
ROLE_SQL+="BEGIN "
ROLE_SQL+="IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN "
ROLE_SQL+="EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', role_name, role_password); "
ROLE_SQL+="END IF; "
ROLE_SQL+="END \$\$;"

sudo -u postgres psql -v ON_ERROR_STOP=1 -c "${ROLE_SQL}"

DB_EXISTS="$(
  sudo -u postgres psql -v ON_ERROR_STOP=1 --tuples-only --no-align \
    -c "SELECT 1 FROM pg_database WHERE datname = ${DB_NAME_LITERAL};"
)"

if [[ "${DB_EXISTS}" != "1" ]]; then
  sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"
fi

echo "Postgres bootstrap complete for ${DB_NAME}"
