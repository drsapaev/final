# W2D API Reference Authentication and Users Verification

## Summary

This was a bounded docs-vs-code verification pass for `docs/API_REFERENCE.md`.

The goal was not to rewrite the full API document. The goal was to correct
high-confidence drift in the `Authentication` and `Users` sections after the
recent auth-adjacent cleanup and settings restoration work.

## Findings

### Authentication section mixed live surfaces and stale request shapes

- the doc only highlighted `/authentication/*`
- current mounted auth surfaces also include:
  - `POST /api/v1/auth/login`
  - `GET /api/v1/auth/me`
- `POST /api/v1/authentication/refresh` currently uses a JSON body with
  `refresh_token`, not a bearer token in the `Authorization` header
- `POST /api/v1/authentication/login` now returns a richer response with
  `refresh_token`, `user`, and 2FA-related fields

### Users section still advertised a removed route and stale access notes

- the doc still advertised `GET /users/me`
- current current-user profile route is `GET /api/v1/auth/me`
- the live self-service user route under `/users/*` is
  `GET/PUT /api/v1/users/me/preferences`
- `GET /api/v1/users/users` is authenticated, not `Admin only`
- `GET /api/v1/users/users/{user_id}` is staff-gated, while
  `PUT/DELETE /api/v1/users/users/{user_id}` remain `Admin`-gated

## What changed

- updated the `Last Verified Slice` note in `docs/API_REFERENCE.md`
- expanded the `Authentication` section to cover both the lightweight
  `/auth/*` surface and the broader `/authentication/*` session/profile surface
- corrected the `refresh` and `logout` request shapes
- replaced stale `/users/me` documentation with the live
  `/users/me/preferences` and `/users/users*` routes
- downgraded the stale `Admin only` claim on `GET /users/users`

## Evidence used

- `backend/openapi.json`
- `backend/app/api/v1/endpoints/auth.py`
- `backend/app/api/v1/endpoints/authentication.py`
- `backend/app/api/v1/endpoints/user_management.py`

## Recommended next step

Continue the broader `API_REFERENCE.md` verification track with another bounded
slice instead of attempting a full rewrite.

Best next candidates:

- `Queue`
- `Payments`
