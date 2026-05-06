## Summary

- Update a backend endpoint and its frontend consumer.
- Preserve documented compatibility behavior for existing callers.

## Contract Impact

- Canonical surface: GET /api/v1/registrar/services
- Request shape: authenticated request, no request body
- Response shape: grouped service dictionary keyed by canonical service group
- Status codes: 200 for allowed users, 401 unauthenticated, 403 forbidden role
- Frontend consumer: registrar service selector
- Compatibility path or alias: legacy code-prefix fallback remains compatibility only
- Contract proof: targeted backend contract test and frontend consumer mapping test

## RBAC / Permissions

- Roles allowed: admin, registrar
- Roles denied: doctor, patient
- Positive auth proof: registrar token returns 200
- Negative auth proof: patient token returns 403

## Notification / Realtime

not applicable - no notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience

- Empty data proof: empty group renders stable empty selector state
- Partial data proof: missing optional description does not crash the selector
- Forbidden secondary path behavior: not applicable, no secondary path used
- Missing draft/resource behavior: not applicable, service selector does not create or reopen drafts/resources
- Stale route/deep-link behavior: not applicable, service selector does not read deep-link route state

## Scope Gate

- Allowed paths: backend registrar endpoint, frontend registrar consumer, targeted regression tests
- Denied paths: unrelated admin panels, migrations, generated output
- Migration/docs/test impact: no migration; targeted tests updated
- Rollback note: revert endpoint, consumer, and targeted tests

## Validation

- Targeted tests or smoke run: backend contract regression and frontend consumer mapping test
- Result: passed
- Not checked: full browser panel smoke
