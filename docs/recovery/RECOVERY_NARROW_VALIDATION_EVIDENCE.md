# Recovery Narrow Validation Evidence

## Commands Run

| command | scope | result |
|---|---|---|
| `git diff --check` | patch hygiene | pass |
| workflow YAML parse on touched GitHub Actions files | CI syntax sanity | pass |
| backend import smoke (`from app.main import app`) | dependency-range sanity | pass |
| `python -m pytest tests/unit/test_notification_endpoint_inventory.py tests/unit/test_notification_platform_contract.py -q` | targeted backend regression | pass |
| forbidden-artifact scan against `backend/clinic.db`, `.claude/settings.local.json`, `.cursor/`, `storage/`, `output/`, `test-results/` | artifact hygiene | pass |

## Intentionally Not Run
- Browser smoke
- Full frontend build
- Broad runtime regression suites

Reason: the narrow branch contains docs, workflow, and dependency-manifest changes only.

## Residual Risks
- Remote GitHub Actions execution still provides the final signal for workflow changes.
- Widened backend constraints were validated in the current environment, not across every future package version in the allowed ranges.
