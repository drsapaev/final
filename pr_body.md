### 💡 What
Added `aria-busy={loading}` to the `ModernButton` component.
Created the required `.Jules/palette.md` for tracking critical UX learnings.

### 🎯 Why
When a button triggers an asynchronous action, standard loading spinners provide visual feedback, but screen reader users miss this context. `aria-busy` solves this natively.

### 📸 Before/After
Before: `<button disabled={loading}>`
After: `<button disabled={loading} aria-busy={loading}>`

### ♿ Accessibility
Significantly improves assistive tech support (NVDA, VoiceOver) by explicitly signaling the component's processing state during network requests or delayed actions.

## Summary

- Added `aria-busy={loading}` to `ModernButton.jsx`
- Created `.Jules/palette.md` for UX tracking
- Improves screen reader accessibility

## Contract Impact

not applicable - No API, websocket, event, or frontend consumer contract changed.

## RBAC / Permissions

not applicable - No route, endpoint, guard, role helper, or auth-sensitive behavior changed.

## Notification / Realtime

not applicable - No notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience

- Empty data proof: Visual change only
- Partial data proof: Visual change only
- Forbidden secondary path behavior: Visual change only
- Missing draft/resource behavior: Visual change only
- Stale route/deep-link behavior: Visual change only

## Scope Gate

- Allowed paths: frontend/src/components/buttons/ModernButton.jsx
- Denied paths: None
- Migration/docs/test impact: None
- Rollback note: Simple revert

## Validation

- Targeted tests or smoke run: `pnpm test src/design-system/components/__tests__/Button.test.jsx`
- Result: Pass
- Not checked: None
