# Settings theme preferences bootstrap

## Root Cause
- `PUT /api/v1/users/me/preferences` tried to create a fresh `UserPreferences` row for a user who had no linked `UserProfile`.
- The insert reached Postgres with `profile_id = NULL`, so the request failed with a `NOT NULL` violation instead of persisting the theme change.
- Live user `#45` had no `profile`, `preferences`, or `notification_settings` rows before the fix, so the settings panel could not rely on preexisting support records.

## Fix
- `UserManagementApiRepository.ensure_user_support_records()` now bootstraps or repairs the support bundle for the current user:
  - `UserProfile`
  - `UserPreferences`
  - `UserNotificationSettings`
- `UserManagementApiService.update_current_user_preferences()` now uses that bootstrap path before mutating theme/language/compact mode/sidebar state.
- The preferences write path now always receives a resolved non-null `profile_id`.

## Verification
- Targeted unit tests passed for both the service and repository bootstrap paths.
- Direct smoke against the live backend returned `200` for `PUT /api/v1/users/me/preferences`.
- Browser smoke on `/admin/benefit-settings?section=settings` confirmed:
  - `Темная` persisted across reload
  - cleanup restored `Авто`
- Evidence captured in:
  - `output/playwright/settings-theme-smoke-final.png`
  - `output/playwright/settings-theme-smoke-network.log`

## Prevention
- Before mutating user preferences, ensure the dependent profile/preferences/settings rows exist or are repaired first.
- Treat preference persistence as a bootstrap-aware workflow, not as a guaranteed preseeded state.
