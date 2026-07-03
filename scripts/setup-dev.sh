#!/usr/bin/env bash
# Bootstrap a fresh checkout for local development.
#
# Installs:
# - Python pre-commit hooks (gitleaks, ruff, black, eslint, custom guards)
# - Frontend node_modules
# - Backend Python deps (assumes venv is already active — see QUICK_START)
#
# Run from repo root: bash scripts/setup-dev.sh
# Idempotent — safe to re-run.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "→ [1/4] Verifying tools..."
command -v python3 >/dev/null || { echo "Missing python3"; exit 1; }
command -v node    >/dev/null || { echo "Missing node";    exit 1; }
command -v npm     >/dev/null || { echo "Missing npm";     exit 1; }

if ! python3 -m pip show pre-commit >/dev/null 2>&1; then
  echo "→ Installing pre-commit..."
  python3 -m pip install --user pre-commit
fi

echo "→ [2/4] Installing pre-commit hooks..."
pre-commit install
pre-commit install --install-hooks -t pre-commit -t commit-msg

echo "→ [3/4] Installing frontend deps..."
cd frontend
npm install --no-audit --no-fund
cd "$REPO_ROOT"

echo "→ [4/4] Installing backend deps..."
cd backend
if [ -n "${VIRTUAL_ENV:-}" ]; then
  echo "  (using active venv: $VIRTUAL_ENV)"
  pip install -r requirements.txt
  # Optional monitoring stack (Sentry + Prometheus). Install only if you
  # plan to run with monitoring enabled locally.
  if [ -f requirements-monitoring.txt ]; then
    read -r -p "Install monitoring deps (Sentry + Prometheus)? [y/N] " yn
    case "$yn" in
      [Yy]*) pip install -r requirements-monitoring.txt ;;
      *) echo "  Skipped — run 'pip install -r requirements-monitoring.txt' to enable." ;;
    esac
  fi
else
  echo "  ⚠️  No active venv. Create one with: python3 -m venv .venv && source .venv/bin/activate"
  echo "  Then re-run this script."
fi

cd "$REPO_ROOT"
echo ""
echo "✅ Setup complete."
echo ""
echo "Next steps:"
echo "  1. cp frontend/.env.example frontend/.env.local  # then edit"
echo "  2. cp backend/.env.example backend/.env          # then edit"
echo "  3. cd backend && alembic upgrade head"
echo "  4. cd backend && uvicorn app.main:app --reload --port 18000"
echo "  5. (other terminal) cd frontend && npm run dev"
echo ""
echo "Pre-commit will run on every commit. To run manually:"
echo "  pre-commit run --all-files"
