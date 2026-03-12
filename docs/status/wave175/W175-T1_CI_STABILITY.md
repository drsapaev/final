# W1.75-T1 CI Stability Recheck

Date: 2026-03-06  
Branch: `codex/w175-gate-readiness`  
Status: `partial`

## Commands Executed

### Frontend

```bash
cd frontend
npm run test:run
npm run test:run
```

Results:
- Run 1: `24` test files passed, `173` tests passed, exit code `0`
- Run 2: `24` test files passed, `173` tests passed, exit code `0`

### Backend

```bash
cd backend
pytest -q
```

Result:
- exit code `1`
- collection/runtime instability due `test_cart_direct.py` (`SystemExit: 1`) after login failure (`401`).

Additional diagnostic run:

```bash
cd backend
pytest tests -q
```

Result:
- `648 passed`, exit code `0`

### RBAC checks

```bash
cd backend
pytest tests/integration/test_rbac_matrix.py -q
python scripts/ci/validate_role_integrity.py
```

Results:
- `test_rbac_matrix.py`: `19 passed`, exit code `0`
- `validate_role_integrity`: `role.integrity.check.success`, exit code `0`

### Workflow snapshot (GitHub Actions)

Evidence commands:

```bash
gh run list --workflow ci-cd-unified.yml --limit 8 --json ...
gh run list --workflow role-system-check.yml --limit 8 --json ...
gh run list --workflow security-scan.yml --limit 8 --json ...
```

Observed:
- Unified CI on `main`: latest known `main` runs remain red for SHA `32e7ee...` (runs `22748643145`, `22717403048`).
- No newer `main` unified run observed that proves post-W1.5 green state.
- `role-system-check` recent `main` runs are green.
- `security-scan` recent `main` runs are green.

## Flaky / Unstable Signal Assessment

- Flaky frontend tests: **not observed** in two consecutive full runs.
- Flaky RBAC matrix: **not observed**.
- Unstable backend root check: **observed** (`pytest -q` over backend root collects non-suite script with side effects).
- CI confidence gap: main unified workflow has stale red state; local stability improved but repository-level green gate is not yet re-proven on `main`.

## Why Status Is `partial`

- Required checks were executed with evidence.
- However, `pytest -q` (as requested) is not stable in current repository root context and remains a blocker signal for gate readiness.
