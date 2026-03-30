# W1.96 Test Fix (TwoFactorManager / tokenManager mismatch)

Date: 2026-03-06  
Branch: `codex/w196-ci-recovery`  
Status: `done`

## CI Failure Signature

From unified run `22748643145` (`🎨 Frontend тесты`):
- failing step: `🧪 Тесты frontend`
- error:
  - `[vitest] No "tokenManager" export is defined on the "../../../utils/tokenManager" mock`
  - trace reached `src/api/client.js` and `src/components/security/TwoFactorManager.jsx`

## Root Cause

The old test mocking strategy expected a `tokenManager` export shape that did not match module usage path during `TwoFactorManager` import chain in CI.

## Minimal Fix Applied

File:
- `frontend/src/components/security/__tests__/TwoFactorManager.test.jsx`

Change approach:
1. Replace fragile `tokenManager`-oriented mock path with direct mock of `../../../api/client`.
2. Mock `api.get/api.post/api.delete` explicitly via `vi.hoisted`.
3. Remove brittle `global.fetch` test plumbing and assert on API client calls used by component logic.

Scope constraints respected:
- no frontend business logic changes
- no component architecture changes
- no backend changes
- test-only targeted patch

## Why This Fix Is Correct

- `TwoFactorManager` consumes API client methods; mocking the same boundary avoids export-shape drift.
- Fix addresses the exact CI error class (`mock/export mismatch`) without broad refactor.
- Local clean and post-fix test runs confirm deterministic pass.

