# W1.95 Security Baseline Recheck

Date: 2026-03-06  
Branch: `codex/w195-gate-recheck`  
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

## Current Baseline

### Backend dependencies (`pip-audit`)

- vulnerable packages: `15`
- vulnerability records: `33`
- delta vs Wave 1.75: **no change** (`15/33`)

### Backend static analysis (`bandit`)

Full scan (`bandit -r .`) executed and parsed from JSON artifact.

Comparable app-scope metrics:
- total: `158`
- high: `15`
- medium: `16`
- low: `127`
- `B701`: `11`
- `B324`: `4`

Delta vs Wave 1.75 app-scope: **no change**.

### Frontend dependencies (`npm audit`)

- total: `11`
- critical: `1`
- high: `3`
- moderate: `7`

Delta vs Wave 1.75: **no change** (`11`, `1 critical`, `3 high`, `7 moderate`).

## Comparison to Wave 1.5 Slice A

Relative to `W15-T4_SECURITY_SLICE_A`:
- risk reduction from Wave 1 baseline remains preserved;
- no additional reductions were achieved in Wave 1.95 recheck;
- `jspdf` critical remains unresolved.

## Applied Human-Review Risk Treatment

1. Payment `B324` in protected paths: accepted risk with mitigation, architectural migration deferred.
2. Print/PDF `B701`: deferred for controlled hardening slice (no behavior-breaking auto-fix).
3. AI/Telegram `B701`: documented as non-browser false-positive class for XSS gating.
4. `jspdf`: major upgrade deferred with temporary mitigation.

## What Was Fixed in W1.95

- No new security code remediation patch was applied in this pass.
- This step is a baseline re-evaluation + decision application pass.

## Critical Risks Remaining

1. Frontend `jspdf` advisory remains critical until major-upgrade/remediation slice is executed.
2. Backend dependency vulnerability set (`15/33`) remains unresolved as debt.

