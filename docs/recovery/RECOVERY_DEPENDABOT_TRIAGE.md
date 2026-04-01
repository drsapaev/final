# Recovery Dependabot Triage

## Scope
- Stage executed: `Stage 2 - Safe cherry-pick triage and execution`
- Method: inspect candidate diff against current execution branch, then either apply the smallest safe equivalent change or record `DROP / NO-OP`
- Rule preserved: `no blind merge of historical branches`

| ref name | package(s) | why still needed or not | action taken | tests run | outcome | regression risk | final verdict |
|---|---|---|---|---|---|---|---|
| `dependabot/github_actions/actions/checkout-6` | `actions/checkout` | Current `main` already uses `actions/checkout@v6` across the affected workflows, so the shortlist signal was stale | drop | direct version inspection in current workflows | no-op | low | `DROP / already superseded by main` |
| `dependabot/github_actions/actions/setup-node-6` | `actions/setup-node` | Current `main` already uses `actions/setup-node@v6` in the affected workflows | drop | direct version inspection in current workflows | no-op | low | `DROP / already superseded by main` |
| `dependabot/github_actions/actions/setup-python-6` | `actions/setup-python` | Current `main` already uses `actions/setup-python@v6` in the affected workflows | drop | direct version inspection in current workflows | no-op | low | `DROP / already superseded by main` |
| `origin/dependabot/github_actions/actions/upload-artifact-7` | `actions/upload-artifact` | Current workflows still had mixed `v4` / `v5` usage on the candidate-covered files | manual reapply | Python `yaml.safe_load(...)` over touched workflow files; `git diff --check` | applied and committed as `8992af7a` | low | `DONE` |
| `origin/dependabot/github_actions/docker/build-push-action-7` | `docker/build-push-action` | Current `main` still used `v6` for the Docker build steps in `ci-cd-unified.yml` | manual reapply | Python `yaml.safe_load(...)` over `ci-cd-unified.yml`; `git diff --check` | applied and committed as `04123a15` | low | `DONE` |
| `origin/dependabot/pip/backend/alembic-gte-1.13-and-lt-1.19` | `alembic` | Constraint on `main` was still `<1.18`; widening to `<1.19` remains useful and low-risk | manual reapply | backend import smoke via `from app.main import app`; `python -m pytest tests/unit/test_notification_endpoint_inventory.py tests/unit/test_notification_platform_contract.py -q`; `git diff --check` | applied and committed as `b89fdbea` | low | `DONE` |
| `origin/dependabot/pip/backend/fastapi-gte-0.121-and-lt-0.136` | `fastapi` | Constraint on `main` was still `<0.130`; widening to `<0.136` remains useful | manual reapply | backend import smoke; targeted pytest; `git diff --check` | applied and committed as `2f049450` | low | `DONE` |
| `origin/dependabot/pip/backend/pydantic-gte-2.7-and-lt-2.13` | `pydantic` | Constraint on `main` was still `<2.12`; widening to `<2.13` remains useful | manual reapply | backend import smoke; targeted pytest; `git diff --check` | applied and committed as `3a44df2d` | low | `DONE` |
| `origin/dependabot/pip/backend/uvicorn-standard--gte-0.29-and-lt-0.43` | `uvicorn[standard]` | Constraint on `main` was still `<0.39`; widening to `<0.43` remains useful | manual reapply | backend import smoke; targeted pytest; `git diff --check` | applied and committed as `6cd41122` | low | `DONE` |
| `origin/dependabot/pip/backend/redis-gte-5.0-and-lt-8.0` | `redis` | Constraint on `main` was still `<6.0`; widening to `<8.0` remains useful | manual reapply | backend import smoke; targeted pytest; `git diff --check` | applied and committed as `398f18e6` | low | `DONE` |

## Notes
- The shortlist turned out to be partially stale: three GitHub Actions bumps were already present on current `main` and were therefore dropped as `NO-OP`.
- The stage used `manual reapply` instead of `cherry-pick` for accepted items because the candidates overlapped heavily on the same workflow files and dependency manifests; this kept the imported change surface minimal and avoided dragging stale branch context.
- One `actions/upload-artifact@v4` occurrence remains in `ci-cd-unified.yml` outside the original candidate-covered slice. It is recorded as residual follow-up, not silently widened beyond the packet-proven scope.
