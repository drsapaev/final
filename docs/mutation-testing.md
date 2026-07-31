# Mutation Testing Setup

**Status:** Configuration ready. Requires tool installation to run.

## Backend (Python) — mutmut

### Installation
```bash
cd backend
pip install mutmut
```

### Configuration
Already in `backend/pyproject.toml` (add this section):
```toml
[tool.mutmut]
paths_to_mutate = [
  "app/services/appointments.py",
  "app/services/payments.py",
  "app/services/queue.py",
  "app/services/emr.py",
]
tests_dir = "tests/"
```

### Run
```bash
cd backend
mutmut run
mutmut results    # summary
mutmut html       # HTML report in html/
```

### Target
- Mutation score >= 80% on critical modules
- Surviving mutants indicate missing test coverage

## Frontend (TypeScript) — Stryker

### Installation
```bash
cd frontend
npm install --save-dev @stryker-mutator/core @stryker-mutator/vitest-runner
```

### Configuration
Already in `frontend/stryker.config.mjs`:
- Mutates: state machines (4 files) + invariants (4 files) + mappers (3 files)
- Test runner: vitest
- Threshold: >= 70% mutation score (break below 70%)
- Coverage analysis: perTest (faster)

### Run
```bash
cd frontend
npx stryker run
```

### Target
- Mutation score >= 70% on state machines and mappers
- HTML report in `frontend/reports/mutation/`

## What mutation testing catches

Mutation testing verifies test quality by injecting small code changes
(mutants) and checking if tests catch them:

| Mutant type | Example | What it tests |
|-------------|---------|---------------|
| Arithmetic  | `a + b` → `a - b` | Math correctness |
| Comparison  | `>` → `>=` | Boundary conditions |
| Boolean     | `true` → `false` | Logic branching |
| Conditional | `if (x)` → `if (true)` | Dead code |
| String      | `"error"` → `""` | Error messages |
| Array       | `[1,2,3]` → `[]` | Array handling |

Surviving mutants = tests don't catch the bug = missing test coverage.

## CI Integration

Add to CI pipeline:
```yaml
# Backend mutation (weekly — slow)
- name: Mutation tests (backend)
  run: |
    cd backend
    pip install mutmut
    mutmut run --paths-to-mutate app/services/appointments.py,app/services/payments.py
    mutmut results | grep -q "survived: 0" || exit 1

# Frontend mutation (weekly — slow)
- name: Mutation tests (frontend)
  run: |
    cd frontend
    npx stryker run --thresholds.break 70
```

Mutation tests are slow (minutes to hours) — run weekly, not on every PR.
