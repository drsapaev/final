## Summary
Fix hardcoded Russian strings in `aria-label` attributes across several custom macOS UI components.

💡 **What**: Replaced hardcoded Russian text like `"Закрыть"` with `t('common.close')` (and `t('misc.fm_aria_close')` for the dialog) in `Alert.tsx`, `Dialog.tsx`, and `Modal.tsx`. Initialized `useTranslation` hook inside the `Alert` component.

🎯 **Why**: Using hardcoded strings limits internationalization and poses problems when changing the application's locale. Utilizing the already existing translation hook makes these labels accessible across supported languages.

📸 **Before/After**: Visually no change, but the `aria-label` attribute on close buttons now reacts to the active language setup properly.

♿ **Accessibility**: Improves accessibility specifically for non-Russian screen reader users who need the "close" actions translated for context.

## Cyclic Execution Evidence
not applicable - Simple attribute replacement with translation functions. No complex state or layout changes involved.

## Contract Impact
not applicable - Simple attribute replacement with translation functions. No complex state or layout changes involved.

## RBAC / Permissions
not applicable - Simple attribute replacement with translation functions. No complex state or layout changes involved.

## Notification / Realtime
not applicable - Simple attribute replacement with translation functions. No complex state or layout changes involved.

## Frontend Resilience
not applicable - Simple attribute replacement with translation functions. No complex state or layout changes involved.

## Scope Gate
- Allowed paths: frontend/src/components/ui/macos/Alert.tsx, frontend/src/components/ui/macos/Dialog.tsx, frontend/src/components/ui/macos/Modal.tsx
- Denied paths: other components, backend, docs, etc.
- Migration/docs/test impact: No migration expected, no new test needed since visual hasn't changed.
- Rollback note: revert the component file changes

## Validation
- Targeted tests or smoke run: Frontend linting and test suites (`pnpm lint:check` and `pnpm test --run`).
- Result: passed
- Not checked: Backend behaviors, as this is purely frontend text replacement.
