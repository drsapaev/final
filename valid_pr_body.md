## Summary
Fix hardcoded Russian strings in `aria-label` attributes across several custom macOS UI components.

💡 **What**: Replaced hardcoded Russian text like `"Закрыть"` with `t('common.close')` (and `t('misc.fm_aria_close')` for the dialog) in `Alert.tsx`, `Dialog.tsx`, and `Modal.tsx`. Initialized `useTranslation` hook inside the `Alert` component.

🎯 **Why**: Using hardcoded strings limits internationalization and poses problems when changing the application's locale. Utilizing the already existing translation hook makes these labels accessible across supported languages.

📸 **Before/After**: Visually no change, but the `aria-label` attribute on close buttons now reacts to the active language setup properly.

♿ **Accessibility**: Improves accessibility specifically for non-Russian screen reader users who need the "close" actions translated for context.

## Cyclic Execution Evidence
- Fresh main sync: yes
- Clean workspace: yes
- Branch: fix-hardcoded-russian-a11y-labels
- Scope gate: allowed frontend UI components
- Red-check handling: will fix

## Contract Impact
- Canonical surface: not applicable because no backend endpoint changed
- Request shape: not applicable because no backend endpoint changed
- Response shape: not applicable because no backend endpoint changed
- Status codes: not applicable because no backend endpoint changed
- Frontend consumer: not applicable because no backend endpoint changed
- Compatibility path or alias: not applicable because no backend endpoint changed
- Contract proof: not applicable because no backend endpoint changed

## RBAC / Permissions
- Roles allowed: not applicable because no roles changed
- Roles denied: not applicable because no roles changed
- Positive auth proof: not applicable because no roles changed
- Negative auth proof: not applicable because no roles changed

## Notification / Realtime
- Event type or websocket channel: not applicable because no realtime changed
- Payload version / ack behavior: not applicable because no realtime changed
- Read/unread or delivery semantics: not applicable because no realtime changed
- Reconnect/resync proof: not applicable because no realtime changed

## Frontend Resilience
- Empty data proof: not applicable because no data flow changed
- Partial data proof: not applicable because no data flow changed
- Forbidden secondary path behavior: not applicable because no data flow changed
- Missing draft/resource behavior: not applicable because no data flow changed
- Stale route/deep-link behavior: not applicable because no data flow changed

## Scope Gate
- Allowed paths: frontend/src/components/ui/macos/**
- Denied paths: backend/**
- Migration/docs/test impact: none
- Rollback note: revert PR

## Validation
- Targeted tests or smoke run: Frontend linting and tests
- Result: passed
- Not checked: Backend tests
