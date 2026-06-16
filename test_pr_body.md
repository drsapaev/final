## Summary
- Added ARIA `role="status"`, `aria-label="Загрузка..."`, and `aria-busy="true"` attributes to the various skeleton states rendered by `MacOSLoadingSkeleton.jsx`.
- Custom loading skeletons and empty states in complex design system components (Tables, Lists, Stat Cards) lacked standard screen reader announcements. This change ensures screen reader users are notified when these regions are processing or waiting for data, preventing a confusing silent experience.

💡 What: Added ARIA `role="status"`, `aria-label="Загрузка..."`, and `aria-busy="true"` attributes to the various skeleton states rendered by `MacOSLoadingSkeleton.jsx`.
🎯 Why: Custom loading skeletons and empty states in complex design system components (Tables, Lists, Stat Cards) lacked standard screen reader announcements. This change ensures screen reader users are notified when these regions are processing or waiting for data, preventing a confusing silent experience.
📸 Before/After: Not a visual change.
♿ Accessibility: Ensures correct loading state communication for assistive technologies (screen readers) when encountering custom UI elements that use `MacOSLoadingSkeleton.jsx`.

## Contract Impact
not applicable - UI accessibility change only, no API contract changes.

## RBAC / Permissions
not applicable - UI accessibility change only, no auth changes.

## Notification / Realtime
not applicable - UI accessibility change only, no realtime behavior changed.

## Frontend Resilience
not applicable - UI accessibility change only, no user-facing panel or frontend data flow changed.

## Scope Gate
- Allowed paths: frontend/src/components/ui/macos/MacOSLoadingSkeleton.jsx
- Denied paths: backend runtime, database migrations, generated output
- Migration/docs/test impact: No database migration or docs changes needed
- Rollback note: revert the commit

## Validation
- Targeted tests or smoke run: ran `pnpm test` and `pnpm lint` in the frontend directory. Also used `git diff` to verify the added attributes.
- Result: passed
- Not checked: backend behavior, as no backend files were modified.
