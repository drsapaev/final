# W2D API Reference Settings and Notifications Verification

## Summary

This was a bounded docs-vs-code verification pass for `docs/API_REFERENCE.md`.

The goal was not to fully re-document the whole API surface. The goal was to
correct high-confidence drift in the document framing and in the
`Notifications` / `Settings` sections after the recent W2D backend cleanup and
contract-restoration work.

## Findings

### Document framing was stale

- `docs/API_REFERENCE.md` still claimed:
  - `Total Routes: 981 endpoints`
  - `Last Updated: December 2024`
- current backend truth lives in `backend/openapi.json`
- the file functions better as a curated reference than as an exact inventory

### Notifications section had live route/schema drift

- the doc still advertised:
  - `GET /notifications/settings/me`
  - `PUT /notifications/settings/me`
- current OpenAPI publishes:
  - `GET /api/v1/notifications/settings/{user_id}`
  - `PUT /api/v1/notifications/settings/{user_id}`
- current endpoint owner is
  `backend/app/api/v1/endpoints/notifications.py`
- the old example payload with `notification_types` no longer matched the live
  `UserNotificationSettingsResponse` /
  `UserNotificationSettingsUpdate` schemas in `backend/openapi.json`
- `GET /notifications/history` was also documented as a current-user-only route
  with a `channel` filter, while the live route is a broader staff-facing
  history surface with `recipient_id`, `recipient_type`, `notification_type`,
  and `status` filters

### Settings section was live but under-documented

- `GET /api/v1/settings` and `PUT /api/v1/settings` are live and mounted from
  `backend/app/api/v1/endpoints/settings.py`
- the doc was directionally correct, but it did not state the actual response
  shape clearly

## What changed

- reframed `docs/API_REFERENCE.md` as a curated reference with `/openapi.json`
  as the exact inventory source
- updated the `Notifications` section to the live
  `/notifications/settings/{user_id}` routes and current schema shape
- corrected the `Notifications history` query parameters to the live route
- tightened the `Settings` section with the actual response shape

## Recommended next step

Continue the broader `API_REFERENCE.md` verification track with another bounded
slice near the touched areas or another high-drift section, instead of trying
to rewrite the full document in one pass.
