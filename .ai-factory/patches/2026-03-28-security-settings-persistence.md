# 2026-03-28 Security Settings Persistence

## Root Cause
- The admin `Security` panel only stored values in local component state and logged a success message.
- There was no backend-backed persistence path for the security form, so reloads always risked losing the edited password policy settings.

## Fix
- Added a JSON-backed `security_settings` field to `user_preferences`.
- Wired `UnifiedSettings` to load and save the security form through `PUT /api/v1/users/me/preferences`.
- Kept password changes on the separate password tab routed through `POST /auth/password-change`.
- Updated the panel copy so it now reflects click-to-save behavior instead of implying persistence that did not exist.

## Verification
- Applied Alembic migration `0019_user_pref_security_settings`.
- Unit tests passed for user-management preference persistence.
- Live browser reload on `/admin?section=security` preserved `Минимальная длина пароля = 10`.
- Evidence captured in `output/playwright/security-settings-smoke-persisted.png`.
