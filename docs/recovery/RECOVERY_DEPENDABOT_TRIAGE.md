# Recovery Dependabot Triage

## Scope
- Stage executed: `Stage 2 - Safe cherry-pick triage and execution`
- Method: inspect candidate diff against current execution branch, then either apply the smallest safe equivalent change or record `DROP / NO-OP`

| ref name | package(s) | why still needed or not | action taken | tests run | outcome | regression risk | final verdict |
|---|---|---|---|---|---|---|---|
| `dependabot/github_actions/actions/checkout-6` | `actions/checkout` | Current `main` already uses `actions/checkout@v6` across the affected workflows | drop | direct version inspection in current workflows | no-op | low | `DROP / already superseded by main` |
| `dependabot/github_actions/actions/setup-node-6` | `actions/setup-node` | Current `main` already uses `actions/setup-node@v6` in the affected workflows | drop | direct version inspection in current workflows | no-op | low | `DROP / already superseded by main` |
| `dependabot/github_actions/actions/setup-python-6` | `actions/setup-python` | Current `main` already uses `actions/setup-python@v6` in the affected workflows | drop | direct version inspection in current workflows | no-op | low | `DROP / already superseded by main` |
| `origin/dependabot/github_actions/actions/upload-artifact-7` | `actions/upload-artifact` | Current workflows still had mixed `upload-artifact` versions on the candidate-covered files | manual reapply | YAML parse of touched workflows; `git diff --check` | applied | low | `DONE` |
| `origin/dependabot/github_actions/docker/build-push-action-7` | `docker/build-push-action` | Current `main` still used `v6` for the Docker build steps in `ci-cd-unified.yml` | manual reapply | YAML parse of touched workflow; `git diff --check` | applied | low | `DONE` |
| `origin/dependabot/pip/backend/alembic-gte-1.13-and-lt-1.19` | `alembic` | Constraint on `main` was still `<1.18` | manual reapply | backend import smoke; targeted pytest; `git diff --check` | applied | low | `DONE` |
| `origin/dependabot/pip/backend/fastapi-gte-0.121-and-lt-0.136` | `fastapi` | Constraint on `main` was still `<0.130` | manual reapply | backend import smoke; targeted pytest; `git diff --check` | applied | low | `DONE` |
| `origin/dependabot/pip/backend/pydantic-gte-2.7-and-lt-2.13` | `pydantic` | Constraint on `main` was still `<2.12` | manual reapply | backend import smoke; targeted pytest; `git diff --check` | applied | low | `DONE` |
| `origin/dependabot/pip/backend/uvicorn-standard--gte-0.29-and-lt-0.43` | `uvicorn[standard]` | Constraint on `main` was still `<0.39` | manual reapply | backend import smoke; targeted pytest; `git diff --check` | applied | low | `DONE` |
| `origin/dependabot/pip/backend/redis-gte-5.0-and-lt-8.0` | `redis` | Constraint on `main` was still `<6.0` | manual reapply | backend import smoke; targeted pytest; `git diff --check` | applied | low | `DONE` |

## Notes
- The shortlist was partially stale: three GitHub Actions bumps were already present on current `main` and were dropped as `NO-OP`.
- The stage used manual reapply for accepted items to keep the imported change surface minimal and avoid dragging stale branch context.
- The remaining `actions/upload-artifact@v4` occurrence outside the candidate-covered slice was intentionally left for separate follow-up.
