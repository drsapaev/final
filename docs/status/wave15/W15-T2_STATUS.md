# W1.5-T2 Status

Date: 2026-03-06  
Task: Stabilize `test_role_routing.py`  
Branch: `codex/w15-stabilize-role-routing`  
Status: `done`

## Problem Analysis

- Pre-fix `python test_role_routing.py` was non-deterministic:
  - depended on running backend instance, seeded users, and current rate-limit state;
  - produced noisy failures (`401 Пользователь не найден`, then `429 IP заблокирован`) even when RBAC matrix tests were green.
- This made CI/local signal unreliable for role-routing checks.

## Decision Taken

- Implemented option **4**: deterministic replacement based on RBAC matrix check.
- `test_role_routing.py` now:
  - runs `pytest tests/integration/test_rbac_matrix.py -q` as primary gate;
  - supports optional `--live-smoke` (advisory health check) for manual environment diagnostics.

## Why This Is Correct

- Keeps scope strictly in test-signal stabilization.
- Does not modify RBAC business logic, auth flow, middleware, or protected auth policies.
- Aligns role-routing signal with existing deterministic integration suite already used as ground truth in Wave 1.

## Files Changed

- `backend/test_role_routing.py`

## Diff Summary

- Removed environment-coupled credential login loop.
- Added deterministic subprocess wrapper for RBAC matrix pytest.
- Added optional advisory `--live-smoke` mode.
- `git diff --stat`:
  - `1 file changed, 78 insertions(+), 159 deletions(-)`

## Mandatory Test Results

Commands:

```bash
cd backend
python test_role_routing.py
pytest tests/integration/test_rbac_matrix.py -q
```

Results:

- `python test_role_routing.py` -> exit code `0` (`PASS: deterministic RBAC matrix check passed`)
- `pytest tests/integration/test_rbac_matrix.py -q` -> `19 passed`

