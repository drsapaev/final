# W1.75 Security Risk Re-evaluation

Date: 2026-03-06  
Branch: `codex/w175-gate-readiness`  
Status: `done`

## Commands Executed

### Backend

```bash
cd backend
pip-audit --format json
bandit -r .
```

### Frontend

```bash
cd frontend
npm audit
```

## Baseline Comparison

Compared against:
- `docs/security/SECURITY_HOUSEKEEPING_REPORT.md` (Wave 1 baseline)
- `docs/security/wave15/W15-T4_SECURITY_SLICE_A.md`
- `docs/security/wave15/W15-T5_SECURITY_SLICE_B.md`

### Backend dependencies (`pip-audit`)

- Wave 1 baseline: `15` vulnerable packages / `33` vulnerability records.
- Wave 1.75 recheck: `15` vulnerable packages / `33` vulnerability records.
- Delta: **no numerical change**.

Top vulnerable packages remain:
- `aiohttp` (`8`)
- `setuptools` (`5`)
- `cryptography` (`3`)
- `urllib3` (`3`)

### Backend static analysis (`bandit`)

- `bandit -r .` executed successfully (text output captured; UTF-8 mode required on Windows).
- Comparable app-scope metrics (`bandit -r app -f json`) at Wave 1.75:
  - total: `158`
  - high: `15`
  - medium: `16`
  - low: `127`
  - `B701`: `11`
  - `B324`: `4`

Comparison:
- Wave 1 baseline (app-scope): high `18`, `B324=7`.
- Wave 1.5 post-fix: high `15`, `B324=4`.
- Wave 1.75 recheck: **stable at Wave 1.5 level** (no regression, no further reduction).

### Frontend dependencies (`npm audit`)

- Wave 1 baseline: total `16` (`2 critical`, `7 high`, `7 moderate`).
- Wave 1.5 post-slice: total `11` (`1 critical`, `3 high`, `7 moderate`).
- Wave 1.75 recheck: total `11` (`1 critical`, `3 high`, `7 moderate`).

Remaining critical/high set:
- critical: `jspdf`
- high: `minimatch`, `rollup` (transitive), `storybook`

## What Was Fixed (Historical Delta Kept)

- Frontend dependency risk reduction achieved in Wave 1.5 remains preserved.
- Backend non-protected MD5 usage reductions from Wave 1.5 remain preserved (`B324` lowered to `4`).

## What Remains

### Critical

1. `jspdf` critical advisory remains unresolved (major-upgrade path).

### High

1. Payment-zone MD5 findings (`B324`) remain in protected files:
   - `app/services/payment_providers/click.py`
   - `app/services/payment_webhook.py`
2. Template rendering `B701` findings remain (`print/pdf/ai/telegram` paths).
3. Frontend toolchain-related high findings remain (`storybook`, transitive `rollup` path).

## Deferrable vs Non-deferrable

### Can be deferred to bounded Wave 2 slices

- Moderate dependency advisories (no immediate gate-fail evidence in current runtime paths).
- Tooling/transitive high findings requiring coordinated package graph changes.

### Should be treated as gate-sensitive

- `jspdf` critical risk decision (documented separately in `W175_JSPDF_RISK_DECISION.md`).
- Protected payment/template high findings requiring explicit human review.
