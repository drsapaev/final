# Profile UX Tabs Refactor

Date: 2026-03-03

## Scope

- `frontend/src/pages/UserProfile.jsx`
- `frontend/src/components/settings/NotificationPreferences.jsx`
- `frontend/src/components/security/TwoFactorManager.jsx`
- `frontend/src/components/settings/__tests__/NotificationPreferences.test.jsx`
- `frontend/src/components/security/__tests__/TwoFactorManager.test.jsx`

## What Changed

- Unified the visual shell of `/profile` tabs so `Личные данные`, `Уведомления`, and `Безопасность` follow the same macOS card layout.
- Reworked `NotificationPreferences` from per-field autosave into draft-based batch editing with explicit `save / reset / refresh`.
- Added in-flight request deduplication and short cache for notification settings to avoid duplicate `GET /notifications/settings/:userId` calls in React StrictMode.
- Simplified `UserProfile` security tab by removing duplicated outer security cards and delegating the flow to `TwoFactorManager`.
- Added a lower action area to the personal info tab so long-form edits do not require scrolling back to the top just to save.
- Updated `TwoFactorManager` to match real backend schemas for trusted devices and fixed device revoke to use `DELETE /api/v1/2fa/devices/:id`.
- Replaced prompt-like 2FA UX with inline confirm blocks, explicit recovery/devices/logs sections, and clearer backup-code actions.

## Verification

- `npx eslint src/components/settings/NotificationPreferences.jsx src/components/settings/__tests__/NotificationPreferences.test.jsx src/components/security/TwoFactorManager.jsx src/components/security/__tests__/TwoFactorManager.test.jsx src/pages/UserProfile.jsx`
- `npm run test:run -- src/components/settings/__tests__/NotificationPreferences.test.jsx src/components/security/__tests__/TwoFactorManager.test.jsx src/pages/__tests__/UserProfile.test.jsx`

## Notes

- This patch is frontend-only and intentionally does not create a commit.
