# W1.95 Test Signal Recheck

Date: 2026-03-06  
Branch: `codex/w195-gate-recheck`  
Status: `done`

## Commands Executed

### Frontend

```bash
cd frontend
npm run test:run
```

Result:
- exit code: `0`
- `24` test files passed
- `173` tests passed

### Backend

```bash
cd backend
pytest -q
```

Result:
- exit code: `0`
- `645 passed, 3 skipped`

### RBAC

```bash
cd backend
pytest tests/integration/test_rbac_matrix.py -q
python scripts/ci/validate_role_integrity.py
```

Result:
- `test_rbac_matrix.py`: `19 passed`, exit code `0`
- `validate_role_integrity`: `role.integrity.check.success`

## Flaky/Unstable Signal Check

- Frontend flakes: not observed in this pass.
- Backend root entrypoint instability: not observed (previous `SystemExit` collection blocker is no longer present in this run).
- RBAC instability: not observed.

## Comparison with Wave 1.75

1. Frontend signal remained stable (`24/173` green).
2. Backend root check improved from **failed** in Wave 1.75 to **green** in Wave 1.95 (`645 passed, 3 skipped`).
3. RBAC checks remained green and deterministic.

