# Patch: Display settings browser smoke and CORS origin alignment

**Date:** 2026-03-27

## Context

The `display-settings` admin panel loaded fine from direct backend calls, but the live browser smoke on `http://127.0.0.1:5174` still failed because the backend CORS allowlist in `backend/.env` did not include the `5174` origin.

## Changes

- Added `http://localhost:5174` and `http://127.0.0.1:5174` to `backend/.env` `CORS_ORIGINS`
- Restarted the backend so the updated allowlist was loaded by `CORSMiddleware`
- Verified the browser save/reload path on the display settings page after the fix

## Verification

- `OPTIONS /api/v1/admin/display/boards` now returns `Access-Control-Allow-Origin: http://127.0.0.1:5174`
- Browser smoke on `http://127.0.0.1:5174/admin/settings?section=display-settings` loads the board list, saves a changed board configuration, and preserves the updated values after reload

## Notes

This fix only aligns the browser origin with the running dev backend. The display settings persistence itself was already backed by the earlier DB migration and CRUD updates.
