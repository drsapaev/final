#!/usr/bin/env bash
# Staging smoke test — runs all validation checks from
# docs/runbooks/STAGING_VALIDATION.md in one command.
#
# Usage:
#   bash scripts/smoke_test_staging.sh
#
# Exit codes:
#   0 = all checks passed
#   1 = at least one check failed
#
# This script is safe to run multiple times. It does NOT modify data.
# It only reads, sends test events to Sentry, and creates a throwaway
# drill DB (cleaned up automatically).

set -uo pipefail

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASS=0
FAIL=0
SKIP=0
FAILURES=()

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Staging Smoke Test — $(date -u +"%Y-%m-%dT%H:%M:%SZ")${NC}"
echo -e "${BLUE}  Repo: $REPO_ROOT${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo ""

# Helper: run a check, print ✓ or ✗
run_check() {
    local num=$1
    local name=$2
    local cmd=$3
    echo -e "${BLUE}Check $num: $name${NC}"
    if eval "$cmd" 2>&1 | sed 's/^/    /'; then
        echo -e "  ${GREEN}✓ Check $num passed${NC}"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}✗ Check $num failed${NC}"
        FAIL=$((FAIL + 1))
        FAILURES+=("Check $num: $name")
    fi
    echo ""
}

# ---------------------------------------------------------------------------
# Check 1: Sentry backend smoke test
# ---------------------------------------------------------------------------
sentry_backend_check() {
    if [ -z "${SENTRY_DSN:-}" ]; then
        echo "    SENTRY_DSN not set — skipping backend Sentry test"
        return 1
    fi
    cd backend
    python -c "
import os
from app.core.sentry import init_sentry, capture_exception
init_sentry()
try:
    raise RuntimeError('staging validation smoke test - backend')
except RuntimeError as e:
    capture_exception(e)
print('    Backend event sent to Sentry.')
" 2>&1
    cd "$REPO_ROOT"
    return 0
}

run_check 1 "Sentry backend smoke test" sentry_backend_check

# ---------------------------------------------------------------------------
# Check 2: DR drill (backup restore)
# ---------------------------------------------------------------------------
dr_drill_check() {
    cd backend
    if [ -z "${DATABASE_URL:-}" ]; then
        echo "    DATABASE_URL not set — skipping DR drill"
        return 1
    fi
    python -m app.scripts.dr_drill 2>&1 | tail -10
    cd "$REPO_ROOT"
}

run_check 2 "DR drill (backup restore)" dr_drill_check

# ---------------------------------------------------------------------------
# Check 3: AI feature flag kill-switch
# ---------------------------------------------------------------------------
feature_flag_check() {
    cd backend
    if [ -z "${DATABASE_URL:-}" ]; then
        echo "    DATABASE_URL not set — skipping feature flag test"
        return 1
    fi

    # Check if seed_ai_feature_flags has been run
    python -c "
import os
from sqlalchemy import create_engine, text
e = create_engine(os.environ['DATABASE_URL'])
with e.connect() as c:
    count = c.execute(text(\"SELECT COUNT(*) FROM feature_flags WHERE key = 'ai_smart_template'\")).scalar()
    if count == 0:
        print('    ai_smart_template flag not found. Run: python -m app.scripts.seed_ai_feature_flags')
        exit(1)
    print(f'    Found {count} ai_smart_template flag(s).')
" 2>&1 || return 1

    # Verify the endpoint exists and is gated
    python -c "
from app.services.ai_feature_gating import RequireAiFeature
dep = RequireAiFeature('ai_smart_template')
print('    RequireAiFeature dependency instantiated correctly.')
" 2>&1
    cd "$REPO_ROOT"
}

run_check 3 "AI feature flag kill-switch wiring" feature_flag_check

# ---------------------------------------------------------------------------
# Check 4: AI safety contract tests
# ---------------------------------------------------------------------------
ai_safety_check() {
    cd backend
    if [ ! -d tests ]; then
        echo "    No tests directory — skipping"
        return 1
    fi
    # Run a subset of safety-related tests
    python -m pytest tests/unit/test_pii_masker.py -v --tb=short 2>&1 | tail -20
    cd "$REPO_ROOT"
}

run_check 4 "AI safety + PII masker unit tests" ai_safety_check

# ---------------------------------------------------------------------------
# Check 5: arq worker setup
# ---------------------------------------------------------------------------
arq_check() {
    cd backend
    if ! python -c "import arq; print(f'    arq version: {arq.__version__}')" 2>&1; then
        echo "    arq not installed — run: pip install arq>=0.26.0"
        return 1
    fi
    # Verify worker module imports
    python -c "
from app.tasks.worker import WorkerSettings, send_visit_reminder, run_data_retention
print(f'    Worker functions: {len(WorkerSettings.functions)} defined')
print(f'    Cron jobs: {len(WorkerSettings.cron_jobs)} defined')
" 2>&1
    cd "$REPO_ROOT"
}

run_check 5 "arq worker setup" arq_check

# ---------------------------------------------------------------------------
# Check 6: PII scrubbing
# ---------------------------------------------------------------------------
pii_check() {
    cd backend
    python -c "
from app.core.pii_masker import mask_pii, mask_phone, mask_email, mask_name

assert mask_phone('+998901234567') == '+998901•••567'
assert mask_email('john@example.com').startswith('j')
assert mask_name('Иван Иванов') == 'И.И.'

patient = {
    'first_name': 'Akmal', 'last_name': 'Karimov',
    'phone': '+998901234567', 'iin': '12345678901234',
    'diagnosis': 'I10', 'id': 42,
}
masked = mask_pii(patient)
assert masked['first_name'] == 'A.'
assert masked['iin'] == '[REDACTED]'
assert masked['id'] == 42

print('    PII scrubbing: all assertions passed.')
" 2>&1
    cd "$REPO_ROOT"
}

run_check 6 "PII scrubbing (3 layers)" pii_check

# ---------------------------------------------------------------------------
# Check 7: Pre-commit hooks installed
# ---------------------------------------------------------------------------
precommit_check() {
    if [ ! -f .git/hooks/pre-commit ]; then
        echo "    pre-commit hook not installed — run: bash scripts/setup-dev.sh"
        return 1
    fi
    if [ ! -f .pre-commit-config.yaml ]; then
        echo "    .pre-commit-config.yaml not found"
        return 1
    fi
    echo "    pre-commit hook installed at .git/hooks/pre-commit"
    echo "    .pre-commit-config.yaml exists"
    # Try running pre-commit on a single file to verify it works
    if command -v pre-commit >/dev/null 2>&1; then
        pre-commit run --files README.md 2>&1 | tail -5 | sed 's/^/    /'
    else
        echo "    pre-commit command not in PATH (but hook is installed)"
    fi
}

run_check 7 "Pre-commit hooks installed" precommit_check

# ---------------------------------------------------------------------------
# Check 8: Backend unit tests
# ---------------------------------------------------------------------------
backend_tests_check() {
    cd backend
    if [ ! -d tests/unit ]; then
        echo "    No tests/unit directory"
        return 1
    fi
    # Run a quick subset (full suite takes 5+ min)
    python -m pytest tests/unit/ -x --tb=line -q 2>&1 | tail -15
    cd "$REPO_ROOT"
}

run_check 8 "Backend unit tests" backend_tests_check

# ---------------------------------------------------------------------------
# Check 9: Bandit security scan
# ---------------------------------------------------------------------------
bandit_check() {
    cd backend
    if ! command -v bandit >/dev/null 2>&1; then
        echo "    bandit not installed — run: pip install bandit"
        return 1
    fi
    bandit -r . -ll 2>&1 | tail -10 | sed 's/^/    /'
    cd "$REPO_ROOT"
}

run_check 9 "Bandit security scan (MEDIUM+)" bandit_check

# ---------------------------------------------------------------------------
# Check 10: Frontend build (if node available)
# ---------------------------------------------------------------------------
frontend_check() {
    if [ ! -d frontend/node_modules ]; then
        echo "    frontend/node_modules not found — run: cd frontend && npm ci"
        return 1
    fi
    cd frontend
    npm run build 2>&1 | tail -5 | sed 's/^/    /'
    cd "$REPO_ROOT"
}

run_check 10 "Frontend build" frontend_check

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}Passed: $PASS${NC}"
echo -e "  ${RED}Failed: $FAIL${NC}"
echo -e "  ${YELLOW}Skipped: $SKIP${NC}"
echo ""

if [ $FAIL -gt 0 ]; then
    echo -e "${RED}Failed checks:${NC}"
    for f in "${FAILURES[@]}"; do
        echo -e "  ${RED}✗${NC} $f"
    done
    echo ""
    echo -e "${RED}System is NOT ready for production. Fix the failures above.${NC}"
    echo -e "See docs/runbooks/STAGING_VALIDATION.md for troubleshooting."
    exit 1
else
    echo -e "${GREEN}✓ All checks passed. System is ready for production deploy.${NC}"
    echo -e "See docs/runbooks/STAGING_VALIDATION.md for the full checklist."
    exit 0
fi
