#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <public_frontend_url> <backend_base_url>" >&2
  exit 1
fi

PUBLIC_URL="$1"
BACKEND_URL="$2"

echo "Checking backend health..."
curl -fsS "${BACKEND_URL}/api/v1/health"
echo

echo "Checking backend docs..."
curl -fsSI "${BACKEND_URL}/docs" | head -n 5
echo

echo "Checking public frontend..."
curl -fsSI "${PUBLIC_URL}" | head -n 5
