## Summary

- Add or update documentation/process guidance.
- No runtime behavior, API contract, migration, or user-facing flow changed.

## Contract Impact

not applicable - documentation/process only, no API, websocket, event, or frontend consumer contract changed.

## RBAC / Permissions

not applicable - no route, endpoint, guard, role helper, or auth-sensitive behavior changed.

## Notification / Realtime

not applicable - no notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience

not applicable - no user-facing panel or frontend data flow changed.

## Scope Gate

- Allowed paths: docs/**, .github/**, scripts/check_pr_review_template.py when the PR is gate-related
- Denied paths: backend runtime, frontend runtime, migrations, generated output
- Migration/docs/test impact: docs/process only; no migration expected
- Rollback note: revert the docs/process changes

## Validation

- Targeted tests or smoke run: local PR review body checker when the PR changes the template or gate
- Result: passed
- Not checked: runtime app behavior, because no runtime files changed
