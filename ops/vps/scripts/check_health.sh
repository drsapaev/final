#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -gt 2 ]]; then
  echo "Usage: $0 [public_url] [backend_url]" >&2
  exit 1
fi

if [[ $# -ge 1 && -n "${1}" ]]; then
  export PUBLIC_URL="${1}"
fi

if [[ $# -ge 2 && -n "${2}" ]]; then
  export BACKEND_URL="${2}"
fi

exec python3 "${SCRIPT_DIR}/health_check.py"
