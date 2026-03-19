#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <db_user> <db_password> <db_name>" >&2
  exit 1
fi

DB_USER="$1"
DB_PASSWORD="$2"
DB_NAME="$3"

sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}') THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', '${DB_USER}', '${DB_PASSWORD}');
    END IF;
END
\$\$;
SQL

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
  sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"
fi

echo "Postgres bootstrap complete for ${DB_NAME}"
