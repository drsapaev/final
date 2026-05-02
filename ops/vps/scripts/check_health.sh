#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PUBLIC_URL="${1:-${PUBLIC_URL:-}}"
export BACKEND_URL="${2:-${BACKEND_URL:-}}"

exec python3 "${SCRIPT_DIR}/health_check.py"
