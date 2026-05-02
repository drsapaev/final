# Surgical Validation Evidence

## Validation commands

### 1) Whitespace / patch sanity
- Command: `git diff --check`
- Result: `PASS`

### 2) Workflow YAML parse
- Command: parsed all `.github/workflows/*.yml` with `yaml.safe_load`
- Result: `PASS`
- Parsed files:
  - `.github/workflows/ci-cd-unified.yml`
  - `.github/workflows/format-code.yml`
  - `.github/workflows/load-testing.yml`
  - `.github/workflows/monitoring.yml`
  - `.github/workflows/role-system-check.yml`
  - `.github/workflows/security-scan.yml`

### 3) Backend import smoke
- Command: imported `fastapi`, `pydantic`, `uvicorn`, `redis`
- Result: `PASS`
- Versions observed:
  - `fastapi 0.129.2`
  - `pydantic 2.11.10`
  - `uvicorn 0.38.0`
  - `redis 5.3.1`

### 4) Targeted backend pytest
- Command: `python -m pytest tests/unit/test_notification_endpoint_inventory.py tests/unit/test_notification_platform_contract.py -q`
- Result: `PASS`
- Outcome: `8 passed in 10.99s`

### 5) Forbidden artifact scan
- Command: checked `git diff --name-only origin/main...HEAD` for forbidden prefixes
- Result: `PASS`

## Intentionally skipped
- No frontend runtime/browser smoke: this narrow branch contains no frontend runtime code.
- No broad regression sweep: the recovery packet is docs + dependency/CI only.
- No GitHub Actions execution locally: remote checks already exist for the PR.

## Residual risk
- Dependency upper-bound bumps are still subject to full remote CI and future dependency churn.
- Recovery docs remain historical evidence and should not be treated as product runtime truth.
