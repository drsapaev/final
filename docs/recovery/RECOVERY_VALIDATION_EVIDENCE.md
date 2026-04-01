# Recovery Validation Evidence

## Commands Run

| command | scope | result | notes |
|---|---|---|---|
| `git -C C:\\final-execution diff --check` | whitespace / patch hygiene | pass | Run after Stage 1, during each accepted Stage 2 item, and at final validation |
| `python - <<yaml.safe_load(...)` over changed workflow files | GitHub Actions YAML integrity | pass | Local surrogate for workflow syntax validation; no local GitHub Actions runner was used |
| `python - <<import fastapi, pydantic, alembic, redis, uvicorn; from app.main import app>>` | backend import/startup smoke | pass | Confirmed current environment imports plus app bootstrap after dependency-range updates |
| `python -m pytest tests/unit/test_notification_endpoint_inventory.py tests/unit/test_notification_platform_contract.py -q` | targeted backend regression | pass | Final run: `8 passed` |
| `git -C C:\\final-execution diff --name-only 959d457b8c1f9883a310f12b790c72e1dd4c1c19..HEAD` with forbidden-artifact scan | artifact hygiene | pass | No forbidden shared artifacts introduced |

## Intentionally Skipped

| check | why skipped |
|---|---|
| targeted frontend vitest | No frontend runtime code changed in this execution branch |
| frontend build | No frontend/runtime code changed; scope was docs, workflows, and backend dependency manifests only |
| browser smoke | No panel / queue / EMR / notifications runtime code changed |
| real GitHub Actions dry run / remote workflow execution | No local GitHub Actions runner was available in the repo workflow; YAML validation was used locally and remote CI remains a review gate |
| fresh environment dependency resolution against the new upper bounds | Execution scope stayed conservative and avoided mutating the local Python environment beyond existing installs; residual risk is documented for review/CI |

## Residual Risk
- Workflow action bumps were validated locally for YAML integrity, but not executed inside GitHub Actions during this recovery run.
- Backend dependency updates widen upper bounds; local validation confirms current installed versions and targeted tests, but not every future version inside the widened ranges.
- One `actions/upload-artifact@v4` occurrence remains in `ci-cd-unified.yml` outside the original packet-proven candidate slice and was intentionally left untouched to avoid widening scope.
