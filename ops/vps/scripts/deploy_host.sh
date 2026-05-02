#!/usr/bin/env bash
set -euo pipefail

: "${APP_ENV:=staging}"
: "${APP_HOST:?APP_HOST is required}"
: "${APP_ROOT:=/opt/clinic}"
: "${RUN_AS_USER:=$(whoami)}"

BACKEND_DIR="${APP_ROOT}/backend"
FRONTEND_DIR="${APP_ROOT}/frontend"
OUTPUT_DIR="${APP_ROOT}/output/vps"
NGINX_TEMPLATE="${APP_ROOT}/ops/vps/nginx/clinic.conf.template"
SERVICE_TEMPLATE="${APP_ROOT}/ops/vps/systemd/clinic-backend.service.template"
NGINX_TARGET="/etc/nginx/sites-available/clinic-${APP_ENV}.conf"
NGINX_LINK="/etc/nginx/sites-enabled/clinic-${APP_ENV}.conf"
SERVICE_TARGET="/etc/systemd/system/clinic-backend-${APP_ENV}.service"
BACKEND_ENV_FILE="${BACKEND_DIR}/.env.${APP_ENV}"
FRONTEND_ENV_FILE="${FRONTEND_DIR}/.env.${APP_ENV}"

if [[ ! -f "${BACKEND_ENV_FILE}" ]]; then
  echo "Missing ${BACKEND_ENV_FILE}" >&2
  exit 1
fi

if [[ ! -f "${FRONTEND_ENV_FILE}" ]]; then
  echo "Missing ${FRONTEND_ENV_FILE}" >&2
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"

python3 -m venv "${BACKEND_DIR}/.venv"
"${BACKEND_DIR}/.venv/bin/pip" install --upgrade pip
"${BACKEND_DIR}/.venv/bin/pip" install -r "${BACKEND_DIR}/requirements.txt"

pushd "${BACKEND_DIR}" >/dev/null
set -a
source "${BACKEND_ENV_FILE}"
set +a
if [[ "${SKIP_MIGRATIONS:-0}" != "1" ]]; then
  "${BACKEND_DIR}/.venv/bin/alembic" upgrade head
  "${BACKEND_DIR}/.venv/bin/alembic" current
fi
popd >/dev/null

pushd "${FRONTEND_DIR}" >/dev/null
npm ci --legacy-peer-deps --include=dev
npm run build -- --mode "${APP_ENV}"
popd >/dev/null

sed \
  -e "s|__APP_HOST__|${APP_HOST}|g" \
  -e "s|__APP_ROOT__|${APP_ROOT}|g" \
  "${NGINX_TEMPLATE}" | sudo tee "${NGINX_TARGET}" >/dev/null

sudo ln -sfn "${NGINX_TARGET}" "${NGINX_LINK}"

sed \
  -e "s|__APP_ENV__|${APP_ENV}|g" \
  -e "s|__APP_ROOT__|${APP_ROOT}|g" \
  -e "s|__RUN_AS_USER__|${RUN_AS_USER}|g" \
  "${SERVICE_TEMPLATE}" | sudo tee "${SERVICE_TARGET}" >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable "clinic-backend-${APP_ENV}"
sudo systemctl restart "clinic-backend-${APP_ENV}"
sudo nginx -t
sudo systemctl restart nginx

echo "Deploy complete for ${APP_ENV}"
echo "Backend docs: http://127.0.0.1:18000/docs"
echo "Public URL: http://${APP_HOST}"
