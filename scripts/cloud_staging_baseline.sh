#!/usr/bin/env bash
# Deliberately runs only on the GitHub-hosted disposable Ubuntu runner.
set -Eeuo pipefail

[[ "${GITHUB_ACTIONS:-}" == true && "${RUNNER_ENVIRONMENT:-}" == github-hosted ]] || {
    echo "Refusing to run outside a disposable GitHub-hosted runner." >&2
    exit 64
}
[[ "${GITHUB_RUN_ID:-}" =~ ^[0-9]+$ && "${GITHUB_RUN_ATTEMPT:-}" =~ ^[0-9]+$ ]]
[[ "${GITHUB_SHA:-}" =~ ^[a-f0-9]{40}$ && "$(git rev-parse HEAD)" == "$GITHUB_SHA" ]]
[[ -z "$(git status --porcelain)" ]]
unset DOCKER_HOST DOCKER_CONTEXT
export DOCKER_HOST=unix:///var/run/docker.sock
project="clinic-staging-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
filter="label=com.docker.compose.project=$project"
env_file="$(mktemp "${RUNNER_TEMP:?}/clinic-composition.XXXXXX")"
overlay="$(mktemp "${RUNNER_TEMP:?}/clinic-compose-overlay.XXXXXX")"
svc_key="$(openssl rand -hex 32)"
docker_cmd=(env -i "PATH=$PATH" "HOME=$HOME" "DOCKER_HOST=$DOCKER_HOST" docker)
compose=("${docker_cmd[@]}" compose --project-directory "$PWD/ops" --project-name "$project" --env-file "$env_file" -f ops/compose.staging.yml -f "$overlay")

baseline=FAIL
cleanup() {
    local rc=$? teardown=FAIL containers networks volumes images
    trap - EXIT INT TERM
    if "${compose[@]}" down -v --remove-orphans --rmi local &&
       containers="$("${docker_cmd[@]}" ps -aq --filter "$filter")" &&
       networks="$("${docker_cmd[@]}" network ls -q --filter "$filter")" &&
       volumes="$("${docker_cmd[@]}" volume ls -q --filter "$filter")" &&
       images="$("${docker_cmd[@]}" image ls -q --filter "$filter")" &&
       [[ -z "$containers$networks$volumes$images" ]]; then
        teardown=PASS
    fi
    rm -f -- "$env_file" "$overlay"
    {
        printf '### Cloud staging baseline · `%s`\n\n' "$GITHUB_SHA"
        printf '| Check | Result |\n|---|---|\n'
        printf '| Isolated Compose, revision, migrations, synthetic data | %s |\n' "$baseline"
        printf '| Teardown | %s |\n' "$teardown"
        printf '| Full staging smoke and external delivery | NOT_RUN |\n'
        printf '| Release admission | NOT_RUN |\n'
        printf '\nGate D runs separately on pushes to main. This result does not authorize deployment.\n'
    } >> "${GITHUB_STEP_SUMMARY:?}"
    [[ "$teardown" == PASS ]] || exit 1
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cat > "$env_file" <<ENV
POSTGRES_USER=clinic
POSTGRES_PASSWORD=$(openssl rand -hex 16)
POSTGRES_DB=clinic_staging
SECRET_KEY=$svc_key
ADMIN_USERNAME=staging-ci
ADMIN_PASSWORD=${svc_key}Aa1!
ADMIN_EMAIL=staging-ci@example.invalid
ADMIN_FULL_NAME=Synthetic CI
APP_VERSION=$GITHUB_SHA
VERCEL_GIT_COMMIT_SHA=$GITHUB_SHA
STAGING_PUBLIC_HOST=127.0.0.1
STAGING_PUBLIC_BASE_URL=http://127.0.0.1:18080
STAGING_PUBLIC_WS_URL=ws://127.0.0.1:18080
STAGING_PUBLIC_WS_HOST=127.0.0.1:18080
CORS_ORIGINS=http://127.0.0.1:18080
SENTRY_DSN=
VITE_SENTRY_DSN=
TELEGRAM_BOT_TOKEN=
ENV

cat > "$overlay" <<'YAML'
services:
  frontend:
    healthcheck:
      test: ["CMD-SHELL", "wget -Y off -q -O /dev/null http://127.0.0.1/"]
YAML

"${compose[@]}" config --quiet
"${compose[@]}" up --build --wait --wait-timeout 240
"${compose[@]}" exec -T backend python -m app.synthetic_seed --count-patients 8 --count-visits 0 --confirm-synthetic-seed
"${compose[@]}" exec -T backend python - <<'PY'
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.db.session import engine

expected = ScriptDirectory.from_config(Config("alembic.ini")).get_heads()
with engine.connect() as db:
    actual = db.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    total, synthetic = db.execute(text(
        "SELECT count(*), count(*) FILTER (WHERE starts_with(last_name, 'SYNTHETIC-')) FROM patients"
    )).one()
assert len(expected) == 1 and expected == actual, (expected, actual)
assert (total, synthetic) == (8, 8), (total, synthetic)
PY

python3 - "$GITHUB_SHA" <<'PY'
import json
import sys
from urllib.request import build_opener, ProxyHandler

sha = sys.argv[1]
http = build_opener(ProxyHandler({}))

def get(url):
    with http.open(url, timeout=10) as response:
        return response.read()

backend = json.loads(get("http://127.0.0.1:18001/"))
assert backend["version"] == sha
assert b"const BUILD_VERSION = '" + sha.encode() + b"';" in get("http://127.0.0.1:18080/sw.js")
assert json.loads(get("http://127.0.0.1:18080/api/v1/health"))["db"] == "ok"
PY
baseline=PASS
