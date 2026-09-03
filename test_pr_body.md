## Summary
Fix hardcoded Russian strings in `aria-label` attributes across several custom macOS UI components.

💡 **What**: Replaced hardcoded Russian text like `"Закрыть"` with `t('common.close')` (and `t('misc.fm_aria_close')` for the dialog) in `Alert.tsx`, `Dialog.tsx`, and `Modal.tsx`. Initialized `useTranslation` hook inside the `Alert` component.

🎯 **Why**: Using hardcoded strings limits internationalization and poses problems when changing the application's locale. Utilizing the already existing translation hook makes these labels accessible across supported languages.

📸 **Before/After**: Visually no change, but the `aria-label` attribute on close buttons now reacts to the active language setup properly.

♿ **Accessibility**: Improves accessibility specifically for non-Russian screen reader users who need the "close" actions translated for context.

## Cyclic Execution Evidence
- Fresh main sync: not applicable
- Clean workspace: not applicable
- Branch: not applicable
- Scope gate: not applicable
- Red-check handling: not applicable

## Contract Impact
- Canonical surface: not applicable
- Request shape: not applicable
- Response shape: not applicable
- Status codes: not applicable
- Frontend consumer: not applicable
- Compatibility path or alias: not applicable
- Contract proof: not applicable

## RBAC / Permissions
- Roles allowed: not applicable
- Roles denied: not applicable
- Positive auth proof: not applicable
- Negative auth proof: not applicable

## Notification / Realtime
- Event type or websocket channel: not applicable
- Payload version / ack behavior: not applicable
- Read/unread or delivery semantics: not applicable
- Reconnect/resync proof: not applicable

## Frontend Resilience
- Empty data proof: not applicable
- Partial data proof: not applicable
- Forbidden secondary path behavior: not applicable
- Missing draft/resource behavior: not applicable
- Stale route/deep-link behavior: not applicable

## Scope Gate
- Allowed paths: not applicable
- Denied paths: not applicable
- Migration/docs/test impact: not applicable
- Rollback note: not applicable

## Validation
- Targeted tests or smoke run: not applicable
- Result: not applicable
- Not checked: not applicable
