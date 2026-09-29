## Summary

- Implemented `useTranslation` in `Input.tsx` to handle the native clear button's `aria-label` and `title`.
- Used `t('common.clear', { defaultValue: 'Clear input' })` to support i18n while maintaining fallback behavior.
- Resolves accessibility and i18n concerns regarding hardcoded English text in interactive elements.

## Cyclic Execution Evidence

- Fresh main sync: branch created from current origin/main
- Clean workspace: inspected before edits; only scoped components and test files changed
- Branch: palette/translate-input-clear-button
- Scope gate: allowed frontend components, denied backend runtime and migrations
- Red-check handling: fix any failed CI check in this same PR before merge

## Contract Impact

not applicable - no API, websocket, event, or frontend consumer contract changed.

## RBAC / Permissions

not applicable - no route, endpoint, guard, role helper, or auth-sensitive behavior changed.

## Notification / Realtime

not applicable - no notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience

not applicable - no user-facing panel or frontend data flow changed.

## Scope Gate

- Allowed paths: frontend/src/components/ui/macos/Input.tsx, .Jules/palette.md
- Denied paths: backend runtime, backend endpoints, migrations, unrelated components
- Migration/docs/test impact: No migration expected. Added to journal.
- Rollback note: revert the component changes

## Validation

- Targeted tests or smoke run: `pnpm lint:check`, `pnpm test` in frontend directory
- Result: passed
- Not checked: runtime app behavior on full browser stack
