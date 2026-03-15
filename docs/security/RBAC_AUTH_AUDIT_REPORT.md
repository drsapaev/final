# RBAC/Auth Audit Report

Date: 2026-03-06  
Task: W1-T3  
Contract: `.ai-factory/contracts/audit-rbac.contract.json`  
Status: `pending human review`

## Scope

- Auth/RBAC audit only.
- No behavior refactor or protected-domain rewrite performed.
- No auth code edits were applied in this wave task.

## Mandatory Checks

### 1) `python test_role_routing.py`

- Result: **failed** (`0/8` users passed).
- Observed errors:
  - `401 {"detail":"Пользователь не найден"}`
  - then `429 IP заблокирован...` after repeated failed login attempts.
- Interpretation:
  - Script is environment-dependent (expects running server with known seeded users and rate-limit-safe state).
  - Failing result is real and must be reported; it is not hidden.

### 2) `pytest tests/integration/test_rbac_matrix.py -q`

- Result: **passed** (`19 passed`).

### 3) `npm run test:run -- src/test/parity/rbacRouteParity.test.js`

- Result: **passed** (`4 passed`).

## Additional Integrity Check

- `python scripts/ci/validate_role_integrity.py --verbose`
- Result: **passed** (`role.integrity.check.success`).

## Findings

1. There is a reproducibility gap between:
   - live-host role script (`test_role_routing.py`) and
   - deterministic RBAC test suite (`test_rbac_matrix.py`) / CI fallback checker.
2. `test_role_routing.py` can trigger local rate limits and produce false-negative operational signals if executed against unseeded or non-reset environment.
3. RBAC matrix + parity checks are currently green, but the environment-dependent script should be reworked into deterministic fixture-driven validation.

## Required Human Review Items

- Decide whether `test_role_routing.py` should remain a mandatory local check in current form.
- Approve a bounded follow-up to make the script deterministic (or demote it to non-blocking diagnostics).
- Confirm no auth-policy change is needed before next wave.

## Commands Executed

- `python test_role_routing.py`
- `pytest tests/integration/test_rbac_matrix.py -q`
- `npm run test:run -- src/test/parity/rbacRouteParity.test.js`
- `python scripts/ci/validate_role_integrity.py --verbose`
